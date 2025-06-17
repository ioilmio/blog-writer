from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
from slugify import slugify
import os
from langchain_ollama import ChatOllama
from langchain_tavily import TavilySearch
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END, START
from backend.llm import get_llm
from backend.llm.neo4j_rag import upsert_article_in_neo4j, retrieve_similar_articles
from neo4j import GraphDatabase
import uuid
import json
from fastapi import BackgroundTasks, Request
from threading import Lock
import re  # Ensure re is imported at the top
import logging
from random import randint

try:
    import colorlog
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s%(levelname)-8s%(reset)s %(white)s%(message)s",
        log_colors={
            'DEBUG':    'cyan',
            'INFO':     'green',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'bold_red',
        }
    ))
    logger = colorlog.getLogger('backend')
    logger.addHandler(handler)
    logger.setLevel('INFO')
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('backend')

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
    image_tags: Optional[List[str]] = None
    content: str

# Nel tuo file backend/main.py (o dove si trova la funzione save_article)

@app.post("/api/save")
async def save_article(article: Article):
    logger.info(f"[SAVE] Saving article: {article.title} (Slug: {article.slug})") # Log più pulito
    try:
        # RIMUOVIO QUESTO BLOCCO: non è necessario e causa il problema
        # import json as _json
        # content = article.content
        # if isinstance(content, str) and content.strip().startswith('{'):
        #     try:
        #         parsed = _json.loads(content)
        #         if isinstance(parsed, dict) and 'content' in parsed:
        #             logger.warning('[SAVE] Detected JSON in article.content, auto-extracting real content.')
        #             content = parsed['content']
        #     except Exception as e:
        #         logger.warning(f'[SAVE] Could not parse article.content as JSON: {e}')

        # Il contenuto di `article.content` dovrebbe essere già il Markdown corretto qui
        content_to_save = article.content 

        # Ensure slug is valid and not empty
        slug = article.slug or slugify(article.title)
        if not slug:
            # Fallback per slug vuoto
            slug = slugify(article.title or "articolo-senza-titolo")
            logger.warning(f"[SAVE] Slug was empty, generated new slug: {slug}")

        save_dir = os.path.join("blog-post", slugify(article.topic or "generale")) # Aggiunto fallback per topic
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, f"{slug}.md")
        
        # Generate markdown content (no leading newline, no JSON)
        markdown_content = (
            f"---\n"
            f"title: \"{article.title}\"\n"
            f"date: \"{article.date}\"\n"
            f"excerpt: \"{article.excerpt}\"\n"
            f"slug: \"{slug}\"\n"
            f"topic: \"{article.topic}\"\n" # topic è nel frontmatter dell'output finale
            f"tags: {article.tags}\n"
            f"image_tags: {article.image_tags if article.image_tags else []}\n"
            f"---\n\n"
            f"{content_to_save}\n" # Usa il contenuto Markdown puro
        )
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        logger.info(f"[SAVE] Article saved to {file_path}")
        # Upsert article in Neo4j after saving, using the Article Pydantic model
        # (This was already in generate_article_endpoint, ensure it's not duplicated if moved)
        # await upsert_article_in_neo4j(article.model_dump()) 
        return {"message": "Article saved successfully", "path": file_path}
    except Exception as e:
        logger.error(f"[ERROR] Failed to save article: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class OverallState(BaseModel):
    topic: str
    additional_context: str = ""
    customer_audience: Optional[bool] = None
    information_type: Optional[str] = None
    output_dir: Optional[str] = None  # workflow-level only
    professional_copy: Optional[str] = None  # NEW
    search_query: str = ""
    web_search_results: dict = {}
    sources: list = []
    summary: str = ""
    article: Optional[dict] = None  # Use None as default
    enrichment: Optional[str] = ""
    image_tags: Optional[List[str]] = None

# Node: Generate web search query using LLM
async def generate_search_query(state: OverallState):
    audience = "clienti in cerca di servizi" if state.customer_audience else "professionisti del settore"
    prompt = f"""
    Il tuo compito è generare una **query di ricerca web altamente mirata e specifica** per trovare le informazioni più attuali e rilevanti sull'argomento. La query deve essere ottimizzata per un motore di ricerca, considerando il **pubblico specifico** e l'**obiettivo informativo** dell'articolo finale.

    **Argomento dell'Articolo:** {state.topic}
    **Pubblico di Riferimento:** {audience}
    **Contesto Aggiuntivo Rilevante:** {state.additional_context}

    La query deve essere concisa e massimizzare la pertinenza dei risultati.
    Rispondi **esclusivamente** con la query racchiusa tra <query> e </query>.

    Esempio di output desiderato: <query>strategie marketing parrucchieri successo 2025</query>
    """
    logger.info(f"[generate_search_query] Prompt: {prompt}")
    llm = get_llm()
    try:
        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        content = getattr(response, 'content', response)
        if not isinstance(content, str):
            content = str(content)
        match = re.search(r"<query>(.*?)</query>", content, re.DOTALL)
        if not match:
            logger.warning("[generate_search_query] No <query> tag found in response. Using topic as query.")
            query = state.topic
        else:
            query = match.group(1).strip()
        logger.info(f"[generate_search_query] Result: {query}")
        return {"search_query": query}
    except Exception as e:
        logger.error(f"[generate_search_query] ERROR: {e}")
        return {"search_query": state.topic}

# Node: Perform web search
async def perform_web_search(state: OverallState):
    tavily = TavilySearch(max_results=5, topic="general")
    try:
        results = tavily.invoke({"query": state.search_query})
        sources = [f"* {r['title']} : {r['url']}" for r in results.get('results', [])]
        logger.info(f"[Web Search] Results: {sources}")
        return {"web_search_results": results, "sources": sources}
    except Exception as e:
        logger.error(f"[Web Search] ERROR: {e}")
        return {"web_search_results": {"results": []}, "sources": []}

# Node: Summarize sources using LLM
async def summarize_sources(state: OverallState):
    logger.info(f"[summarize_sources] State: {state}")
    # Defensive: ensure web_search_results is a dict with 'results' key
    results = getattr(state, 'web_search_results', {})
    if isinstance(results, dict):
        result_list = results.get('results', [])
    else:
        result_list = []
    search_snippets = "\n".join([r.get('content','') for r in result_list if isinstance(r, dict)])
    audience = "clienti in cerca di servizi" if state.customer_audience else "professionisti del settore"
    
    # Determinazione dello scopo/tipo di informazione per guidare il riassunto
    information_purpose = ""
    if state.information_type:
        information_purpose = f"Il riassunto dovrà evidenziare in particolare: {state.information_type}. "

    prompt = f"""
    Genera un **riassunto completo, coerente e di alta qualità** basato sui seguenti risultati di ricerca web. Questo riassunto sarà la **fonte primaria di informazioni** per la creazione di un articolo dettagliato sul blog di Mestieri.pro.

    **Obiettivo del Riassunto:** Fornire una base solida e organizzata per un articolo destinato a un pubblico di **{audience}** e incentrato sull'argomento: **{state.topic}**.
    {information_purpose}Assicurati di estrarre e sintetizzare in modo chiaro:
    -   I **punti chiave e concetti fondamentali**.
    -   I **dati più recenti e rilevanti** (statistiche, studi).
    -   I **consigli pratici e le best practice** applicabili.
    -   Le **ultime tendenze e sviluppi** nel settore.
    -   Le **informazioni normative o legali** aggiornate, se pertinenti.
    -   Eventuali **sfide comuni e le relative soluzioni**.

    Organizza il riassunto in modo logico, facilitando la successiva stesura dell'articolo. Non includere opinioni personali o informazioni non supportate dai risultati forniti.

    **Contesto Aggiuntivo Rilevante:** {state.additional_context}
    **Risultati di Ricerca da Sintetizzare:**
    {search_snippets}

    Rispondi **esclusivamente** con il riassunto racchiuso tra <summary> e </summary>.
    """
    logger.info(f"[summarize_sources] Prompt: {prompt}")
    llm = get_llm()
    response = await llm.ainvoke([{"role": "user", "content": prompt}])
    content = getattr(response, 'content', response)
    if not isinstance(content, str):
        content = str(content)
    match = re.search(r"<summary>(.*?)</summary>", content, re.DOTALL)
    summary = match.group(1).strip() if match else ""
    logger.info(f"[summarize_sources] Summary: {summary}")
    return {"summary": summary}

# Node: Enrich with similar articles (RAG)
async def enrich_with_similar_articles_node(state: OverallState):
    # Retrieve top 3 similar articles (hybrid search, filtered by all tags dynamically)
    similar = retrieve_similar_articles(state.topic, top_k=3, use_all_tags=True)
    enrichment = "\n\n".join([
        f"[Riferimento] {item.metadata.get('title', '')}: {item.metadata.get('excerpt', '')}" for item in similar
    ])
    logger.info(f"[enrich_with_similar_articles_node] Enrichment: {enrichment}")
    return {"enrichment": enrichment}

# Node: Generate article daft (LLM)
async def generate_article_node(state: OverallState):
    logger.info(f"[generate_article_node] Generating article with summary context: {state.summary}")
    audience = "consumatori interessati a trovare o capire meglio i servizi offerti dai professionisti." if state.customer_audience else "professionisti del settore che vogliono tenersi aggiornati"
    extra_context = state.additional_context or ""
    enrichment = getattr(state, "enrichment", "")
    if enrichment:
        extra_context += f"\nContesto da articoli simili:\n{enrichment}"
    if state.information_type:
        extra_context += f"\nTipo di informazione: {state.information_type}"
    extra_context += f"\nPubblico: {audience}"
    if state.professional_copy:
        extra_context += f"\nContesto professionale: {state.professional_copy}"
    prompt = f"""
    Sei un esperto redattore per il blog di Mestieri.pro. Il tuo compito è scrivere un **articolo dettagliato, approfondito e originale** di almeno **1200 parole**, basandoti sul materiale di riferimento fornito.
    L'articolo dovrà essere **suddiviso in sezioni con titoli chiari e pertinenti**, e dovrà **includere esempi pratici, consigli avanzati e una forte e persuasiva call to action finale**. Non limitarti a elencare i punti, ma **espandi, spiega e approfondisci ogni concetto** con una prosa fluida e coinvolgente.
    **Pubblico di Riferimento:** {audience}
    **Tipo di Contenuto:** {state.information_type if state.information_type else 'Articolo informativo'}
    **Tono:** Adatta il tono all'argomento e al pubblico, mantenendolo autorevole, utile e coinvolgente.
    **Argomento Principale dell'Articolo:** {state.topic}
    **Contesto Aggiuntivo e Requisiti Specifici:** {extra_context}
    **Materiale di Riferimento Dettagliato (da cui espandere e sviluppare l'articolo):**
    {state.summary}
    Dopo aver completato l'articolo, genera una lista di 3-7 tag descrittivi per immagini.
    Questi tag devono rappresentare visivamente i temi principali, i concetti chiave e le azioni discusse nell'articolo.
    I tag devono essere racchiusi tra <image_tags> e </image_tags>.
    Esempio: <image_tags>fotografo professionista, studio fotografico, scatto ritratto, clienti felici</image_tags>
    **Rispondi solo ed esclusivamente con un oggetto JSON che abbia esattamente questi campi.** Il campo "content" deve contenere l'intero testo dell'articolo in formato Markdown, pronto per essere pubblicato.
    Esempio:
    {{
      "title": "Come aumentare i guadagni come artista di strada",
      "excerpt": "Scopri strategie pratiche per incrementare i tuoi guadagni come artista di strada.",
      "tags": ["arte di strada", "guadagni", "strategie", "eventi"],
      "slug": "come-aumentare-i-guadagni-come-artista-di-strada",
      "content": contenuto in markdown,
      "date": "2025-05-12",
      "image_tags": ["artista di strada", "pubblico", "performance", "strumenti musicali"]
    }}
    Non aggiungere testo fuori dal JSON, non omettere nessun campo, non cambiare i nomi dei campi.
    """
    logger.info(f"[generate_article_node] LLM prompt: {prompt}")
    llm = get_llm()
    response = await llm.ainvoke([{"role": "user", "content": prompt}])
    content = getattr(response, 'content', response)
    if not isinstance(content, str):
        content = str(content)
    import json as _json
    import ast
    try:
        # Robustly extract JSON from code block or extra text
        json_match = re.search(r"```json(.*?)```", content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            brace_idx = content.find('{')
            if brace_idx != -1:
                json_str = content[brace_idx:]
            else:
                raise ValueError("No JSON object found in LLM output.")
        # Sanitize: replace unescaped control characters in string values
        def sanitize_json_string(s):
            # Replace unescaped newlines and tabs inside string values
            s = re.sub(r'(?<!\\)\n', r'\\n', s)
            s = re.sub(r'(?<!\\)\t', r'\\t', s)
            # Special handling for the content field: escape unescaped double quotes inside the value
            def content_replacer(match):
                content_val = match.group(1)
                # Escape unescaped double quotes inside the content value
                content_val = re.sub(r'(?<!\\)"', r'\\"', content_val)
                return f'"content": "{content_val}"'
            s = re.sub(r'"content"\s*:\s*"([\s\S]*?)"\s*,', content_replacer, s)
            return s
        json_str = sanitize_json_string(json_str)
        try:
            parsed = _json.loads(json_str)
        except Exception as json_err:
            # Fallback: try to parse as Python dict (single quotes)
            try:
                # Replace single quotes with double quotes for property names and string values
                # Only if it looks like a dict
                if json_str.strip().startswith("{"):
                    safe_str = re.sub(r"'", '"', json_str)
                    parsed = _json.loads(safe_str)
                else:
                    parsed = ast.literal_eval(json_str)
            except Exception as ast_err:
                logger.error(f"[generate_article_node] Both JSON and ast.literal_eval failed. JSON error: {json_err}, ast error: {ast_err}\nLLM output was: {content}")
                raise HTTPException(status_code=500, detail=f"Failed to parse LLM output as JSON: {json_err}")
        # Validate required fields
        required_fields = ["title", "excerpt", "tags", "content", "slug", "date", "image_tags"]
        for field in required_fields:
            if field not in parsed:
                raise ValueError(f"Missing field in LLM output: {field}")
        start_date = datetime(2024, 12, 17)
        end_date = datetime.now()
        delta_days = (end_date - start_date).days
        random_days = randint(0, delta_days)
        random_date = (start_date + timedelta(days=random_days)).strftime("%Y-%m-%d")
        article = {
            'title': parsed.get('title',''),
            'excerpt': parsed.get('excerpt',''),
            'tags': parsed.get('tags',[]),
            'content': parsed.get('content',''),
            'slug': parsed.get('slug','') or slugify(parsed.get('title', ''), lowercase=True),
            'date': random_date,
            'image_tags': parsed.get('image_tags',[])
        }
        logger.info(f"[generate_article_node] Article generated: {article}")
        return {"article": article}
    except Exception as e:
        logger.error(f"[generate_article_node] Failed to parse LLM response as JSON: {e}\nLLM output was: {content}")
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM output as JSON: {e}")
# Node: Finalize article
async def finalize_article(state: OverallState):
    logger.info(f"[finalize_article] Finalizing article: {state.article}")
    if state.article is None:
        logger.error(f"[finalize_article] state.article is None. State: {state}")
        raise HTTPException(status_code=500, detail="Article generation failed: state.article is None.")
    try:
        start_date = datetime(2024, 12, 17)
        end_date = datetime.now()
        delta_days = (end_date - start_date).days
        random_days = randint(0, delta_days)
        random_date = (start_date + timedelta(days=random_days)).strftime("%Y-%m-%d")
        slug = slugify(state.article['title'], lowercase=True)
        original_content = state.article['content']
        audience = "clienti in cerca di servizi" if state.customer_audience else "professionisti del settore"
        
        # Determine specific context for information type and audience
        info_type_context = f" di tipo '{state.information_type}'" if state.information_type else ""
        audience_context = f" destinato a un pubblico di '{audience}'"

        proofreading_prompt = f"""
            Sei un esperto copywriter e revisore di contenuti per il blog di Mestieri.pro. Il tuo compito è **migliorare, ottimizzare e correggere minuziosamente** il contenuto dell'articolo fornito, rendendolo di altissima qualità, impeccabile e perfettamente allineato agli standard editoriali.

            **Obiettivo Principale:** Assicurare che l'articolo finale sia un contenuto di valore, altamente coinvolgente e utile per il lettore, pronto per la pubblicazione.

            **Istruzioni Dettagliate per la Revisione:**

            1.  **Correzione Linguistica Completa:**
                * Correggi ogni singolo errore **grammaticale, sintattico, ortografico e di punteggiatura**.
                * Assicurati che la **fluidità** del testo sia massima, con frasi ben costruite e transizioni logiche tra i paragrafi.
            2.  **Chiarezza, Concisine e Scorrevolezza:**
                * Elimina ogni ridondanza, ambiguità o informazione superflua. Il testo deve essere **chiaro, diretto e facile da comprendere**.
                * Migliora la scorrevolezza complessiva, rendendo la lettura piacevole e senza intoppi.
            3.  **Tono e Stile Professionale:**
                * Mantieni un **tono coerente, autorevole e professionale**, ma accessibile.
                * Evita rigorosamente anglicismi non necessari, espressioni gergali o eccessivamente colloquiali. Preferisci un **italiano standard, formale ma coinvolgente**.
                * Il tono deve essere perfettamente allineato con quello di un articolo{info_type_context}{audience_context} per Mestieri.pro.
            4.  **Gestione dei Competitor (Cruciale):**
                * **È ASSOLUTAMENTE VIETATO menzionare qualsiasi piattaforma competitor**, inclusi (ma non limitati a) ChronoShare o ProntoPro.
                * Se il testo originale contiene tali riferimenti, **rimuovili completamente o riformulali** in modo neutrale.
                * Se un confronto fosse implicito o inevitabile, focalizzati **esclusivamente sui benefici e i punti di forza unici di Mestieri.pro**, senza mai nominare direttamente i concorrenti. L'attenzione deve rimanere sul valore offerto da Mestieri.pro.
            5.  **Ottimizzazione della Call To Action (CTA):**
                * Verifica che la CTA finale sia **presente, chiara, forte e persuasiva**.
                * Se mancante o debole, **aggiungine o rafforzane una** che inviti specificamente i lettori a:
                    * Esplorare i servizi/professionisti su Mestieri.pro.
                    * I professionisti a iscriversi o scoprire come usare la piattaforma.
                    * Visitare la pagina **https://mestieri.pro/info** per maggiori informazioni.
                * La CTA deve essere il culmine logico dell'articolo.
            6.  **Interazione con il Lettore:**
                * Includi una breve e cortese frase alla fine dell'articolo (dopo la CTA) che inviti i lettori a **condividere l'articolo o lasciare un feedback** per contribuire al miglioramento continuo dei contenuti di Mestieri.pro.
            7.  **Preservazione del Contenuto Originale:**
                * Applica **modifiche mirate e non invasive**. La struttura e il significato fondamentale dell'articolo devono essere preservati. Intervieni solo dove strettamente necessario per migliorare la qualità e la conformità alle istruzioni.

            **RISPONDI ESCLUSIVAMENTE CON IL CONTENUTO DELL'ARTICOLO REVISIONATO E MIGLIORATO.** Non aggiungere commenti, preamboli, introduzioni, conclusioni o qualsiasi altro testo al di fuori dell'articolo finale.

            **Contenuto originale da correggere:**
            {original_content}
            """
        logger.info(f"[finalize_article] Proofreading prompt: {proofreading_prompt}")
        try:
            llm = get_llm()
            improved_content = await llm.ainvoke([{"role": "user", "content": proofreading_prompt}])    
            if hasattr(improved_content, 'content'):
                improved_content = improved_content.content
            if not isinstance(improved_content, str):
                improved_content = str(improved_content)
        except Exception as e:
            logger.error(f"[PROOFREAD ERROR] {e}, using original content.")
            improved_content = original_content
        article = Article(
            title=state.article['title'],
            date=random_date,
            excerpt=state.article['excerpt'],
            slug=slug,
            topic=state.topic,
            tags=state.article['tags'],
            image_tags=state.article.get('image_tags', []),
            content=improved_content
        )
        logger.info(f"[finalize_article] Article finalized: {article}")
        return article
    except Exception as e:
        logger.error(f"[ERROR] Exception in finalize_article: {e}")
        raise HTTPException(status_code=500, detail=f"Exception in finalize_article: {e}")

# --- RAG: Store and retrieve similar articles ---
async def enrich_with_similar_articles(article: Article):
    upsert_article_in_neo4j(article.model_dump())
    # Retrieve top 3 similar articles (hybrid search, filtered by all tags dynamically)
    similar = retrieve_similar_articles(article.content, top_k=3, use_all_tags=True)
    enrichment = "\n\n".join([
        f"[Riferimento] {item.metadata.get('title', '')}: {item.metadata.get('excerpt', '')}" for item in similar
    ])
    logger.info(f"[enrich_with_similar_articles] Enrichment: {enrichment}")
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
    logger.info(f"[API] Generate article request: {article_input}")
    try:
        workflow = get_workflow()
        state = OverallState(
            topic=article_input.topic,
            additional_context=article_input.additional_context or "",
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
        else:
            logger.error(f"[API] Article generation failed, result: {result}")
            raise HTTPException(status_code=500, detail="Article generation failed: No valid article returned.")
        # Ensure topic is always present
        if article and "topic" not in article:
            article["topic"] = article_input.topic
        # Ensure title and slug are always present and valid
        if not article.get('title'):
            article['title'] = article.get('topic', 'Articolo senza titolo')
        if not article.get('slug'):
            article['slug'] = slugify(article['title'], lowercase=True)
        # Only auto-save if autosave flag is set
        if article and getattr(article_input, "autosave", False):
            await save_article(Article(**article))
        # --- RAG enrichment ---
        if article:
            enrichment = await enrich_with_similar_articles(Article(**article))
            article["additional_context"] = enrichment
        return article if article else HTTPException(status_code=500, detail="Article not generated")
    except Exception as e:
        logger.error(f"[API] Exception in generate_article_endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- API endpoint for manual retrieval ---
from fastapi import Query

@app.get("/api/retrieve")
async def retrieve_articles(query: str = Query(..., description="Query for hybrid search")):
    logger.info(f"[API] Retrieve articles request: {query}")
    try:
        results = retrieve_similar_articles(query, top_k=3)
        logger.info(f"[API] Retrieve results: {results}")
        return [{"title": r.metadata.get("title"), "excerpt": r.metadata.get("excerpt"), "slug": r.metadata.get("slug"), "score": getattr(r, "score", None)} for r in results]
    except Exception as e:
        logger.error(f"[API] Exception in retrieve_articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

JOBS_FILE = "pipeline_jobs.json"
jobs_lock = Lock()

# --- Job State Management ---
def load_jobs():
    if not os.path.exists(JOBS_FILE):
        return {}
    with open(JOBS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_jobs(jobs):
    with jobs_lock:
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)

def update_job(job_id, update):
    jobs = load_jobs()
    if job_id not in jobs:
        jobs[job_id] = {}
    jobs[job_id].update(update)
    save_jobs(jobs)

def get_job(job_id):
    jobs = load_jobs()
    return jobs.get(job_id)

# --- Modular Pipeline Steps ---
async def step_generate(article_input):
    logger.info(f"[Pipeline Step] Generate article: {article_input}")
    try:
        result = await generate_article_endpoint(ArticleInput(**article_input))
        logger.info(f"[Pipeline Step] Generate result: {result}")
        return {"status": "waiting_approval", "result": result}
    except Exception as e:
        logger.error(f"[Pipeline Step] Generate error: {e}")
        return {"status": "error", "error": str(e)}

async def step_image(article):
    # Minimal log for step start
    logger.info("[Pipeline Step] Image: started")
    if not article or not article.get('image_tags'):
        logger.warning("[Pipeline Step] Image: No image_tags found in article, skipping image fetch.")
        return {"status": "waiting_approval", "result": article}
    image_tags = article['image_tags']
    logger.info(f"[Pipeline Step] Image: using image_tags: {image_tags}")
    # Call image fetching/validation pipeline (external script or function)
    # Example: fetch_and_insert_images.py expects a markdown file, but you can adapt this to your needs
    # Here, just log the tags and simulate image step
    # TODO: Integrate actual image fetching logic here
    # Remove/comment out any long logs (article content, etc.)
    # Only log minimal info for step tracking
    # Return article unchanged for now, but in real use, update with image info
    logger.info("[Pipeline Step] Image: completed")
    return {"status": "waiting_approval", "result": article}

async def step_upsert(article):
    logger.info(f"[Pipeline Step] Upsert article to DB: {article}")
    try:
        upsert_article_in_neo4j(article)
        logger.info(f"[Pipeline Step] Upsert result: {article}")
        return {"status": "done", "result": article}
    except Exception as e:
        logger.error(f"[Pipeline Step] Upsert error: {e}")
        return {"status": "error", "error": str(e)}

# --- Pipeline Runner ---
async def run_pipeline_job(job_id, job_data):
    logger.info(f"[Pipeline Runner] Starting job: {job_id}, data: {job_data}")
    steps = job_data.get("steps", ["generate", "image", "upsert"])
    article_input = job_data["article_input"]
    state = {}
    for step in steps:
        logger.info(f"[Pipeline Runner] Executing step: {step}")
        if step == "generate":
            res = await step_generate(article_input)
            update_job(job_id, {"current_step": step, "generate": res})
            if res["status"] != "waiting_approval":
                logger.info(f"[Pipeline Runner] Generate step completed: {res}")
                break
            return  # Wait for approval
        elif step == "image":
            job_state = get_job(job_id) or {}
            article = job_state.get("generate", {}).get("result") if job_state.get("generate") else None
            res = await step_image(article)
            update_job(job_id, {"current_step": step, "image": res})
            if res["status"] != "waiting_approval":
                logger.info(f"[Pipeline Runner] Image step completed: {res}")
                break
            return
        elif step == "upsert":
            job_state = get_job(job_id) or {}
            article = job_state.get("image", {}).get("result") if job_state.get("image") else None
            res = await step_upsert(article)
            update_job(job_id, {"current_step": step, "upsert": res})
            if res["status"] != "done":
                logger.info(f"[Pipeline Runner] Upsert step completed: {res}")
                break
    update_job(job_id, {"status": "finished"})
    logger.info(f"[Pipeline Runner] Job finished: {job_id}")

# --- API Endpoints ---
@app.post("/api/pipeline/run")
async def api_pipeline_run(article_input: dict, background_tasks: BackgroundTasks):
    logger.info(f"[API Pipeline] Run pipeline request: {article_input}")
    job_id = str(uuid.uuid4())
    job_data = {"article_input": article_input, "steps": ["generate", "image", "upsert"], "status": "running"}
    update_job(job_id, job_data)
    background_tasks.add_task(run_pipeline_job, job_id, job_data)
    logger.info(f"[API Pipeline] Job enqueued: {job_id}")
    return {"job_id": job_id}

@app.post("/api/pipeline/batch")
async def api_pipeline_batch(batch: dict, background_tasks: BackgroundTasks):
    logger.info(f"[API Pipeline] Batch pipeline request: {batch}")
    job_ids = []
    for article_input in batch.get("articles", []):
        job_id = str(uuid.uuid4())
        job_data = {"article_input": article_input, "steps": batch.get("steps", ["generate", "image", "upsert"]), "status": "running"}
        update_job(job_id, job_data)
        background_tasks.add_task(run_pipeline_job, job_id, job_data)
        job_ids.append(job_id)
        logger.info(f"[API Pipeline] Job enqueued: {job_id}")
    return {"job_ids": job_ids}

@app.get("/api/pipeline/status/{job_id}")
async def api_pipeline_status(job_id: str):
    logger.info(f"[API Pipeline] Status request: {job_id}")
    job = get_job(job_id)
    if not job:
        logger.error(f"[API Pipeline] Job not found: {job_id}")
        raise HTTPException(status_code=404, detail="Job not found")
    logger.info(f"[API Pipeline] Job status: {job}")
    return job

@app.post("/api/pipeline/approve/{job_id}/{step}")
async def api_pipeline_approve(job_id: str, step: str, request: Request, background_tasks: BackgroundTasks):
    logger.info(f"[API Pipeline] Approve request: job_id={job_id}, step={step}")
    data = await request.json()
    job = get_job(job_id)
    if not job:
        logger.error(f"[API Pipeline] Job not found: {job_id}")
        raise HTTPException(status_code=404, detail="Job not found")
    # Update step result with approved/edited data
    job[step]["status"] = "approved"
    job[step]["result"] = data.get("result", job[step]["result"])
    update_job(job_id, job)
    logger.info(f"[API Pipeline] Job updated: {job_id}, step: {step}, status: approved")
    # Resume pipeline from next step
    background_tasks.add_task(run_pipeline_job, job_id, job)
    return {"status": "resumed"}

@app.post("/api/pipeline/retry/{job_id}/{step}")
async def api_pipeline_retry(job_id: str, step: str, background_tasks: BackgroundTasks):
    logger.info(f"[API Pipeline] Retry request: job_id={job_id}, step={step}")
    job = get_job(job_id)
    if not job:
        logger.error(f"[API Pipeline] Job not found: {job_id}")
        raise HTTPException(status_code=404, detail="Job not found")
    # Remove failed step and resume
    if step in job:
        del job[step]
    update_job(job_id, job)
    logger.info(f"[API Pipeline] Job updated for retry: {job_id}, step: {step}")
    background_tasks.add_task(run_pipeline_job, job_id, job)
    return {"status": "retrying"}

@app.get("/health")
def health_check():
    logger.info("[Health Check] Service is up")
    return {"status": "ok"}

