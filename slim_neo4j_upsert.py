"""
slim_neo4j_upsert.py

Upsert a validated article into Neo4j.
"""
import traceback
import yaml
from backend.llm.neo4j_rag import upsert_article_in_neo4j

def upsert_article_from_md(md_path: str) -> bool:
    """
    Upsert the article in md_path to Neo4j. Returns True if successful, False otherwise.
    """
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        parts = content.split('---')
        if len(parts) < 3:
            print(f"[ERROR] Invalid markdown frontmatter format: {md_path}")
            return False
        frontmatter = yaml.safe_load(parts[1])
        article = dict(frontmatter)
        article["content"] = parts[2].strip()
        upsert_article_in_neo4j(article)
        print(f"[OK] Upserted to Neo4j: {md_path}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to upsert {md_path} to Neo4j: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    md_path = "blog-post/dj/dj-clienti-in-cerca-di-servizi-guida-pratica.md"
    upsert_article_from_md(md_path)
