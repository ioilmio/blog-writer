import os
import logging
from neo4j import GraphDatabase
from langchain_neo4j import Neo4jVector
from langchain_ollama import OllamaEmbeddings
from typing import Dict, Any, List
from langchain_text_splitters import CharacterTextSplitter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("neo4j_rag")

# Neo4j connection config
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")

# Embedding model (Ollama local)
EMBEDDING_MODEL = "nomic-embed-text:latest"

# Helper to get Neo4j vector store
def get_neo4j_vector_store(expected_dim: int = 768):
    logger.info(f"Connecting to {NEO4J_URI} as {NEO4J_USER}")
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    # Dimension check
    test_vec = embeddings.embed_query("dimension test")
    actual_dim = len(test_vec)
    logger.info(f"Embedding dimension for model '{EMBEDDING_MODEL}': {actual_dim}")
    if actual_dim != expected_dim:
        logger.error(f"Embedding dimension mismatch: expected {expected_dim}, got {actual_dim}")
        raise ValueError(f"Embedding dimension mismatch: expected {expected_dim}, got {actual_dim}")
    try:
        vectorstore = Neo4jVector(
            url=NEO4J_URI,
            username=NEO4J_USER,
            password=NEO4J_PASSWORD,
            embedding=embeddings,
            database="neo4j",
            index_name="articles",
            embedding_dimension=expected_dim
        )
        logger.info("Vector store initialized.")
        # Explicitly create vector index and log result
        try:
            vectorstore.create_new_index()
            logger.info("Vector index 'articles' created or already exists.")
        except Exception as e:
            logger.warning(f"Vector index creation: {e}")
        # Explicitly create keyword index for hybrid search
        try:
            vectorstore.create_new_keyword_index(["content"])
            logger.info("Keyword index for 'content' created or already exists.")
        except Exception as e:
            logger.warning(f"Keyword index creation: {e}")
    except Exception as e:
        logger.error(f"Error initializing Neo4jVector: {e}")
        raise
    return vectorstore

# Chunking logic for long articles
def chunk_article_content(content: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
    splitter = CharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_text(content)

# Helper to check if article exists by slug
def article_exists(slug: str) -> bool:
    try:
        vectorstore = get_neo4j_vector_store()
        # Use similarity_search with filter for metadata
        results = vectorstore.similarity_search("", k=1, filter={"slug": slug})
        return len(results) > 0
    except Exception as e:
        logger.error(f"Error checking if article exists in Neo4j vector store: {e}")
        return False

# Store article in Neo4j
def store_article_in_neo4j(article: Dict[str, Any]):
    logger.info(f"Storing article: {article.get('title', '[no title]')}")
    try:
        # Extract tags from article (expects 'tags' as a list of strings)
        tags = article.get("tags", [])
        if not isinstance(tags, list):
            tags = [tags] if tags else []
        # Store embeddings in vector DB as before
        vectorstore = get_neo4j_vector_store()
        text_chunks = chunk_article_content(article["content"])
        metadata = {k: v for k, v in article.items() if k != "content"}
        logger.info(f"Metadata: {metadata}")
        logger.info(f"Storing {len(text_chunks)} chunks in vector DB.")
        vectorstore.add_texts(text_chunks, metadatas=[metadata]*len(text_chunks))
        logger.info("Article stored in vector DB.")

        # Store article and tag relationships in Neo4j graph
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session(database="neo4j") as session:
            # Merge article node
            session.run(
                """
                MERGE (a:Article {slug: $slug})
                SET a.title = $title, a.content = $content, a.slug =$slug
                """,
                slug=article.get("slug"),
                title=article.get("title"),
                content=article.get("content"),
            )
            # Merge tag nodes and relationships
            for tag in tags:
                session.run(
                    """
                    MERGE (t:Tag {name: $tag})
                    WITH t
                    MATCH (a:Article {slug: $slug})
                    MERGE (a)-[:HAS_TAG]->(t)
                    """,
                    tag=tag,
                    slug=article.get("slug")
                )
        driver.close()
        logger.info(f"Article node and tag relationships created in Neo4j graph.")
    except Exception as e:
        logger.error(f"Error storing article in Neo4j vector store: {e}")
        raise

# Update article embedding in Neo4j
def update_article_in_neo4j(slug: str, article: Dict[str, Any]):
    logger.info(f"Updating article with slug: {slug}")
    try:
        vectorstore = get_neo4j_vector_store()
        # Delete all vectors with this slug in metadata using filter
        results = vectorstore.similarity_search("", k=100, filter={"slug": slug})
        ids_to_delete = [getattr(r, 'id', None) for r in results if getattr(r, 'id', None)]
        if ids_to_delete:
            vectorstore.delete(ids_to_delete)
            logger.info(f"Deleted {len(ids_to_delete)} old embeddings for slug: {slug}")
        else:
            logger.info(f"No existing embeddings found for slug: {slug}")
        text_chunks = chunk_article_content(article["content"])
        metadata = {k: v for k, v in article.items() if k != "content"}
        logger.info(f"Storing {len(text_chunks)} chunks in vector DB for update.")
        vectorstore.add_texts(text_chunks, metadatas=[metadata]*len(text_chunks))
        logger.info(f"Updated embedding for article slug: {slug}")
    except Exception as e:
        logger.error(f"Error updating article in Neo4j vector store: {e}")
        raise

# Store or update article in Neo4j
def upsert_article_in_neo4j(article: Dict[str, Any]):
    slug = article.get("slug")
    if not slug:
        logger.warning("Article missing slug, cannot upsert.")
        return
    try:
        if article_exists(slug):
            logger.info(f"Article with slug '{slug}' exists, updating.")
            update_article_in_neo4j(slug, article)
        else:
            logger.info(f"Article with slug '{slug}' does not exist, creating.")
            store_article_in_neo4j(article)
    except Exception as e:
        logger.error(f"Error in upsert_article_in_neo4j: {e}")
        raise

# Hybrid search (vector + keyword)
def retrieve_similar_articles(query: str, top_k: int = 3, use_all_tags: bool = False):
    vectorstore = get_neo4j_vector_store()
    filter_dict = {}
    tags = None
    # If use_all_tags is True, dynamically get all tags from Neo4j
    if use_all_tags:
        try:
            tags = get_all_tags_from_neo4j()
            logger.info(f"Retrieving top {top_k} similar articles for query: {query[:60]}..." + (f" with tag(s): {tags}" if tags else ""))
        except Exception as e:
            logger.error(f"Error retrieving tags from Neo4j: {e}")
            tags = None
    if tags:
        filter_dict["tags"] = tags
    try:
        if filter_dict:
            results = vectorstore.similarity_search(query, k=top_k, filter=filter_dict, search_type="hybrid")
        else:
            results = vectorstore.similarity_search(query, k=top_k, search_type="hybrid")
        logger.info(f"Retrieved {len(results)} similar articles.")
        for idx, r in enumerate(results):
            logger.info(f"Result {idx+1}: {getattr(r, 'metadata', {})}")
        return results
    except Exception as e:
        logger.error(f"Error during similarity search: {e}")
        return []

def get_all_tags_from_neo4j() -> List[str]:
    """Retrieve all unique tags from Chunk nodes in Neo4j."""
    driver = GraphDatabase.driver(os.getenv("NEO4J_URI", "bolt://localhost:7687"), auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "testpassword")))
    with driver.session(database="neo4j") as session:
        tag_results = session.run("MATCH (c:Chunk) UNWIND c.tags AS tag RETURN DISTINCT tag")
        all_tags = [record["tag"] for record in tag_results if record["tag"]]
    driver.close()
    return all_tags
