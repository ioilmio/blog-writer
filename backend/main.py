from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
from slugify import slugify
import os
from langchain_ollama import ChatOllama
from langchain_tavily import TavilySearch
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END, START
from backend.llm import generate_article as llm_generate_article, get_llm
from backend.llm.neo4j_rag import upsert_article_in_neo4j, retrieve_similar_articles
from neo4j import GraphDatabase
load_dotenv()

tavily_api_key = os.getenv("TAVILY_API_KEY")  # Access the variable

# def get_llm_reasoner_model():
#     return ChatOllama(
#         model="deepseek-r1:14b",
#         temperature=1
#     )

def extract_result_from_tags(tag: str, result: str):
    if "</think>" in result:
        result = result.split("</think>")[1]
    #Extract using tags

    if f"<{tag}>" in result:
        return result.split(f"<{tag}>")[1].split(f"</{tag}>")[0]

    return result

app = FastAPI()

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ArticleInput(BaseModel):
    topic: str
    additional_context: Optional[str] = None
    customer_audience: Optional[bool] = None
    information_type: Optional[str] = None
    output_dir: Optional[str] = None  # workflow-level only
    autosave: Optional[bool] = False  # workflow-level only
    professional_copy: Optional[str] = None  # NEW

class Article(BaseModel):
    title: str
    date: str
    excerpt: str
    slug: str
    topic: str
    tags: List[str]
    content: str

@app.post("/api/save")
async def save_article(article: Article):
    try:
        # Always fallback to blog-post/[slugified topic] for manual save
        save_dir = os.path.join("blog-post", slugify(article.topic))
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, f"{article.slug}.md")
        
        # Generate markdown content
        markdown_content = f"""
---
title: "{article.title}"
date: "{article.date}"
excerpt: "{article.excerpt}"
slug: "{article.slug}"
topic: "{article.topic}"
tags: {article.tags}
---

{article.content}
"""
        
        # Save the file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        print(f"[SAVE] Article saved to {file_path}")
        return {"message": "Article saved successfully", "path": file_path}
    except Exception as e:
        print(f"[ERROR] Failed to save article: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# import asyncio

class OverallState(BaseModel):
    topic: str
    additional_context: str = ""
    customer_audience: Optional[bool] = None
    information_type: Optional[str] = None
    output_dir: Optional[str] = None  # workflow-level only
    professional_copy: Optional[str] = None  # NEW
    search_query: str = ""
    web_search_results: list = []
    sources: list = []
    summary: str = ""
    article: Optional[dict] = None  # Use None as default
    enrichment: Optional[str] = ""  # Add enrichment to state

# Node: Generate web search query using LLM
async def generate_search_query(state: OverallState):
    audience = "clienti in cerca di servizi" if state.customer_audience else "professionisti del settore"
    prompt = f"""
    Il tuo compito è generare una query di ricerca web mirata per raccogliere informazioni aggiornate sull'argomento seguente, tenendo conto del pubblico a cui è destinato l'articolo.
    Argomento: {state.topic}
    Pubblico: {audience}
    Contesto aggiuntivo: {state.additional_context}
    Rispondi solo con la query racchiusa tra <query> e </query>.
    Esempio: <query>strategie marketing parrucchieri 2025</query>
    """
    print("**************************\n[LLM] Prompt for search query:\n", prompt)
    llm = get_llm()
    try:
        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        print("**************************\n[LLM] Response for search query:\n", response.content)
        import re
        match = re.search(r"<query>(.*?)</query>", response.content, re.DOTALL)
        if not match:
            print("**************************\n[LLM] WARNING: No <query> tag found in response. Using topic as query.")
            query = state.topic
        else:
            query = match.group(1).strip()
        return {"search_query": query}
    except Exception as e:
        print("**************************\n[LLM] ERROR during search query generation:", e)
        print("**************************\n[LLM] Fallback: using topic as query.")
        return {"search_query": state.topic}

# Node: Perform web search
async def perform_web_search(state: OverallState):
    tavily = TavilySearch(max_results=5, topic="general")
    try:
        results = tavily.invoke({"query": state.search_query})
        sources = [f"* {r['title']} : {r['url']}" for r in results.get('results', [])]
        print("[Web Search] Results:", sources)
        return {"web_search_results": results, "sources": sources}
    except Exception as e:
        print("[Web Search] ERROR:", e)
        print("[Web Search] Fallback: empty results.")
        return {"web_search_results": {"results": []}, "sources": []}

# Node: Summarize sources using LLM
async def summarize_sources(state: OverallState):
    print(state, "state")
    search_snippets = "\n".join([r.get('content','') for r in state.web_search_results.get('results', [])])
    audience = "clienti in cerca di servizi" if state.customer_audience else "professionisti del settore"
    prompt = f"""
    Genera un riassunto di alta qualità e altamente informativo dei seguenti risultati di ricerca web per l'argomento: {state.topic}.
    Il riassunto dovrà servire come base per un articolo destinato a un pubblico di {audience} sul blog di Mestieri.pro. Assicurati di estrarre e sintetizzare i punti chiave, i dati rilevanti, i consigli pratici, le tendenze o le informazioni normative più aggiornate presenti nei risultati.
    Contesto aggiuntivo: {state.additional_context}
    Risultati di ricerca:\n{search_snippets}
    Rispondi solo con il riassunto racchiuso tra <summary> e </summary>.
    """
    print("**************************\n[LLM] Prompt for summarization:\n", prompt)
    llm = get_llm()
    response = await llm.ainvoke([{"role": "user", "content": prompt}])
    print("**************************\n[LLM] Response for summarization:\n", response.content)
    import re
    match = re.search(r"<summary>(.*?)</summary>", response.content, re.DOTALL)
    summary = match.group(1).strip() if match else ""
    return {"summary": summary}

# Node: Enrich with similar articles (RAG)
async def enrich_with_similar_articles_node(state: OverallState):
    # Retrieve top 3 similar articles (hybrid search, filtered by all tags dynamically)
    similar = retrieve_similar_articles(state.topic, top_k=3, use_all_tags=True)
    enrichment = "\n\n".join([
        f"[Riferimento] {item.metadata.get('title', '')}: {item.metadata.get('excerpt', '')}" for item in similar
    ])
    return {"enrichment": enrichment}

# Node: Generate article daft (LLM)
async def generate_article_node(state: OverallState):
    print("**************************\n[LLM] Generating article with summary context:", state.summary)
    audience = "consumatori interessati a trovare o capire meglio i servizi offerti dai professionisti." if state.customer_audience else "professionisti del settore che vogliono tenersi aggiornati"
    extra_context = state.additional_context or ""
    # Add enrichment if present
    enrichment = getattr(state, "enrichment", "")
    if enrichment:
        extra_context += f"\nContesto da articoli simili:\n{enrichment}"
    if state.information_type:
        extra_context += f"\nTipo di informazione: {state.information_type}"
    extra_context += f"\nPubblico: {audience}"
    if state.professional_copy:
        extra_context += f"\nContesto professionale: {state.professional_copy}"
    article = await llm_generate_article(
        topic=state.topic,
        additional_context=extra_context + "\n" + state.summary
    )
    print("**************************\n[LLM] Article generated:", article)
    print("**************************\n[LLM] state:", state)
    return {"article": article.model_dump()}

# Node: Finalize article
async def finalize_article(state: OverallState):
    print("**************************\n[DEBUG] finalize_article state.article:", state.article)
    now = datetime.now().strftime("%Y-%m-%d")
    slug = slugify(state.article['title'], lowercase=True)
    # Proofreading step using LLM
    original_content = state.article['content']
    audience = "clienti in cerca di servizi" if state.customer_audience else "professionisti del settore"

    proofreading_prompt = f"""
        Il tuo compito è correggere e migliorare il contenuto fornito, assicurandoti che sia impeccabile dal punto di vista grammaticale, ortografico e della chiarezza.

        **Istruzioni per la correzione:**

        1.  **Grammatica, Sintassi e Ortografia:** Correggi qualsiasi errore grammaticale, di sintassi o ortografico.
        2.  **Chiarezza e Scorrevolezza:** Rendi il testo più chiaro, conciso e scorrevole, eliminando frasi ridondanti o ambigue.
        3.  **Linguaggio:**
            * Evita l'uso di anglicismi inutili o espressioni colloquiali eccessive, preferendo un italiano standard e professionale.
            * Mantieni il tono coerente con quello di un articolo {state.information_type} destinato a {audience} del blog di Mestieri.pro.
        4.  **Contenuto Sensibile (Competitors):**
            * **NON menzionare in alcun modo piattaforme competitor** come ChronoShare o ProntoPro.
            * Se il contenuto originale dovesse per qualche motivo fare riferimento a tali piattaforme, modifica il testo per rimuovere qualsiasi menzione.
            * In caso sia assolutamente necessario un confronto (sebbene da evitare), riformula il testo in modo da evidenziare sempre e solo i vantaggi e i punti di forza di Mestieri.pro, senza nominare direttamente i competitor.

        **Rispondi solo con il contenuto corretto e migliorato, senza aggiungere commenti o preamboli.**

        Contenuto originale da correggere:
        {original_content}
        """
    try:
        llm = get_llm()
        improved_content = await llm.ainvoke([{"role": "user", "content": proofreading_prompt}])    
        if hasattr(improved_content, 'content'):
            improved_content = improved_content.content
    except Exception as e:
        print(f"[PROOFREAD ERROR] {e}, using original content.")
        improved_content = original_content
    return Article(
        title=state.article['title'],
        date=now,
        excerpt=state.article['excerpt'],
        slug=slug,
        topic=state.topic,
        tags=state.article['tags'],
        content=improved_content
    )

# --- RAG: Store and retrieve similar articles ---
async def enrich_with_similar_articles(article: Article):
    upsert_article_in_neo4j(article.model_dump())
    # Retrieve top 3 similar articles (hybrid search, filtered by all tags dynamically)
    similar = retrieve_similar_articles(article.content, top_k=3, use_all_tags=True)
    enrichment = "\n\n".join([
        f"[Riferimento] {item.metadata.get('title', '')}: {item.metadata.get('excerpt', '')}" for item in similar
    ])
    return enrichment

# Build the workflow graph
def get_workflow():
    builder = StateGraph(OverallState)
    builder.add_node("generate_search_query", generate_search_query)
    builder.add_node("perform_web_search", perform_web_search)
    builder.add_node("summarize_sources", summarize_sources)
    builder.add_node("enrich_with_similar_articles", enrich_with_similar_articles_node)
    builder.add_node("generate_article", generate_article_node)
    builder.add_node("finalize_article", finalize_article)
    builder.add_edge(START, "generate_search_query")
    builder.add_edge("generate_search_query", "perform_web_search")
    builder.add_edge("perform_web_search", "summarize_sources")
    builder.add_edge("summarize_sources", "enrich_with_similar_articles")
    builder.add_edge("enrich_with_similar_articles", "generate_article")
    builder.add_edge("generate_article", "finalize_article")
    builder.add_edge("finalize_article", END)
    return builder.compile()

@app.post("/api/generate")
async def generate_article_endpoint(article_input: ArticleInput):
    print("API is running")
    try:
        workflow = get_workflow()
        state = OverallState(
            topic=article_input.topic,
            additional_context=article_input.additional_context,
            customer_audience=article_input.customer_audience,
            information_type=article_input.information_type,
            output_dir=None,  # Do not use output_dir, always use topic-based dir
            professional_copy=article_input.professional_copy,  # NEW
        )
        result = await workflow.ainvoke(state)
        article = None
        if isinstance(result, Article):
            article = result.model_dump()
        elif isinstance(result, dict) and "title" in result:
            article = result
        elif "article" in result and isinstance(result["article"], dict):
            article = result["article"]
            article["date"] = result.get("date") or datetime.now().strftime("%Y-%m-%d")
            article["slug"] = result.get("slug") or slugify(article["title"], lowercase=True)
            article["topic"] = result.get("topic") or state.topic
        # Only auto-save if autosave flag is set
        if article and getattr(article_input, "autosave", False):
            await save_article(Article(**article))
        # --- RAG enrichment ---
        if article:
            enrichment = await enrich_with_similar_articles(Article(**article))
            article["additional_context"] = enrichment
        return article if article else HTTPException(status_code=500, detail="Article not generated")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- API endpoint for manual retrieval ---
from fastapi import Query

@app.get("/api/retrieve")
async def retrieve_articles(query: str = Query(..., description="Query for hybrid search")):
    try:
        results = retrieve_similar_articles(query, top_k=3)
        return [{"title": r.metadata.get("title"), "excerpt": r.metadata.get("excerpt"), "slug": r.metadata.get("slug"), "score": getattr(r, "score", None)} for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

