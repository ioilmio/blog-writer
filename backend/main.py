from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Annotated, Literal
from datetime import datetime
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
from slugify import slugify
import os
from langchain_ollama import ChatOllama
from langchain_tavily import TavilySearch
from dotenv import load_dotenv
load_dotenv()

tavily_api_key = os.getenv("TAVILY_API_KEY")  # Access the variable

def get_llm_reasoner_model():
    return ChatOllama(
        model="deepseek-r1:14b",
        temperature=1
    )

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
    topic: Optional[str] = None
    additional_context: Optional[str] = None
    max_web_search: Optional[int] = 1

class Article(BaseModel):
    title: Optional[str] = None
    date: Optional[str] = None
    excerpt: Optional[str] = None
    slug: Optional[str] = None
    topic: Optional[str] = None
    tags: Optional[List[str]] = None
    content: Optional[str] = None   

class OverallState(): # Removed Article from base classes
    search_query: Optional[str] = None # Make fields optional
    research_loop_count: int = 0
    sources_gathered: Annotated[list[AnyMessage], add_messages] = []
    web_search_results: Annotated[list[AnyMessage], add_messages] = []
    summary: Optional[str] = None
    title: Optional[str] = None
    date: Optional[str] = None
    excerpt: Optional[str] = None
    slug: Optional[str] = None
    tags: Optional[List[str]] = None
    content: Optional[str] = None


def generate_first_query(state: ArticleInput):
    prompt = (
        f"Your goal is to generate a targeted web search query. ... The topic is: {state.topic} ..."
        f"Please return the query wrapped in <query> tags. For example: <query>Suggested query</query>"
    )

    reasoner_llm = get_llm_reasoner_model()  
    response = reasoner_llm.invoke(prompt)
  
    #Extract using tags
    query = extract_result_from_tags("query", response.content) 
    print(query)
    return {"search_query": query}

def get_sources_from_search_results(search_response: dict): # Changed the type hint
    return '\n'.join(
        f"* {source['title']} : {source['url']}"
        for source in search_response['results']
    )

def web_search_generator(state: OverallState):
    search_results = TavilySearch().search(state['search_query'])
    sources = get_sources_from_search_results(search_results) # Added this line

    return {
        "sources_gathered": state.get("sources_gathered", []) + [sources], # corrected
        "web_search_results": state.get("web_search_results", []) + [search_results], # corrected
        "research_loop_count": state.get("research_loop_count", 0) + 1
    }


def summarize_sources(state: OverallState):
    existing_summary = state.get("summary", "")
    last_web_search = state["web_search_results"][-1]
    prompt = (
        f"Generate a high-quality summary of the web search results ... The topic is: {state['topic']} ..."
        f"Existing summary: {existing_summary}" if existing_summary else ""
        f"Search results: {last_web_search}"
        "Please return the summary wrapped in <summary> tags. For example: <summary>Suggested summary</summary>"
    )

    reasoner_llm = get_llm_reasoner_model()
    response = reasoner_llm.invoke(prompt)

    #Extract using tags
    summary = extract_result_from_tags("summary", response.content) 
    return {"summary": summary}


def finalize_summary(state: OverallState):
  unique_sources = list(set(state.get("sources_gathered", [])))
  all_sources = "\n".join(source for source in unique_sources)
  final_summary = f"## Summary\n\n{state['summary']}\n\n ### Sources:\n{all_sources}"
  title = f"Summary of {state['topic']}"
  date=datetime.now().strftime("%Y-%m-%d")
  excerpt=state['summary'][:100] if state['summary'] else ""
  slug=slugify(state['topic'])
  tags=[state['topic']]
  content=state['summary']

  return {"summary": final_summary,
          "title": title,
          "date": date,
          "excerpt": excerpt,
          "slug": slug,
          "tags": tags,
          "content": content
          }

# Removed reflect_on_summary and reasearch_router

from langgraph.graph import StateGraph, END, START

def get_workflow():
    builder = StateGraph(OverallState) # Removed input and output

    # Add nodes
    builder.add_node("generate_first_query", generate_first_query)
    builder.add_node("web_research", web_search_generator)
    builder.add_node("summarize_sources", summarize_sources)
    builder.add_node("finalize_summary", finalize_summary)

    # Add edges
    builder.add_edge(START, "generate_first_query")
    builder.add_edge("generate_first_query", "web_research")
    builder.add_edge("web_research", "summarize_sources")
    builder.add_edge("summarize_sources", "finalize_summary")
    builder.add_edge("finalize_summary", END)

    return builder.compile()

@app.post("/api/generate")
async def generate_article(article_input: ArticleInput):
    print("API is running")
    try:
        workflow = get_workflow()
        result = workflow.invoke({"article_input": article_input})
        article_result = Article( # Create Article object
            title=result['title'],
            date=result['date'],
            excerpt=result['excerpt'],
            slug=result['slug'],
            topic=article_input.topic,
            tags=result['tags'],
            content=result['content']
        )
        return article_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/save")
async def save_article(article: Article):
    try:
        # Create directory based on slugified topic
        topic_dir = slugify(article.topic)
        os.makedirs(topic_dir, exist_ok=True)
        
        # Create file path using slugified title
        file_path = os.path.join(topic_dir, f"{article.slug}.md")
        
        # Generate markdown content
        markdown_content = f"""---
title: "{article.title}"
date: "{article.date}"
excerpt: "{article.excerpt}"
slug: "{article.slug}"
topic: "{article.topic}"
tags: {article.tags}
---

{article.content}"""
        
        # Save the file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
            
        return {"message": "Article saved successfully", "path": file_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
