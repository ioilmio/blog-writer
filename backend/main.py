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
from backend.llm import generate_article as llm_generate_article
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
    topic: str
    additional_context: Optional[str] = None

class Article(BaseModel):
    title: str
    date: str
    excerpt: str
    slug: str
    topic: str
    tags: List[str]
    content: str

@app.post("/api/generate")
async def generate_article(article_input: ArticleInput):
    print("API is running")
    print("article_input", article_input.topic, article_input.additional_context)
    try:
        # Always perform web search here if needed (not implemented in this snippet)
        # Call the LLM with the correct prompt and output format
        article = await llm_generate_article(
            topic=article_input.topic,
            additional_context=article_input.additional_context or ""
        )
        # Add date, slug, topic
        from datetime import datetime
        from slugify import slugify
        now = datetime.now().strftime("%Y-%m-%d")
        slug = slugify(article.title, lowercase=True)
        return Article(
            title=article.title,
            date=now,
            excerpt=article.excerpt,
            slug=slug,
            topic=article_input.topic,
            tags=article.tags,
            content=article.content
        )
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

                            {article.content}
                            """
        
        # Save the file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
            
        return {"message": "Article saved successfully", "path": file_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
