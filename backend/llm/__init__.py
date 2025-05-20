from langchain_ollama import ChatOllama
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List
import json

class BlogArticle(BaseModel):
    title: str = Field(description="The title of the blog article")
    excerpt: str = Field(description="A brief summary of the article")
    tags: List[str] = Field(description="List of relevant tags for the article")
    content: str = Field(description="The main content of the article in markdown format")

# Initialize Ollama with Deepseek model (use the correct model name)

llm = ChatOllama(
    model="deepseek-r1:14b",
    temperature = 0.5,
)
# Template for generating blog articles
BLOG_TEMPLATE = """
Scrivi un articolo di blog in italiano sul seguente argomento: {topic}

Contesto aggiuntivo: {additional_context}

L'articolo deve seguire questo formato:
1. Un titolo accattivante
2. Un breve estratto che riassume l'articolo
3. Tag pertinenti
4. Contenuto principale in formato markdown

{format_instructions}
"""

# Initialize the parser
parser = PydanticOutputParser(pydantic_object=BlogArticle)

# Create the prompt template
prompt = PromptTemplate(
    template=BLOG_TEMPLATE,
    input_variables=["topic", "additional_context"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

async def generate_article(topic: str, additional_context: str = "") -> BlogArticle:
    try:
        _prompt = prompt.format(topic=topic, additional_context=additional_context)
        # Use ainvoke for ChatOllama and pass a list of messages
        response = await llm.ainvoke([
            {"role": "user", "content": _prompt}
        ])
        article = parser.parse(response.content)
        return article
    except Exception as e:
        print("LLM error:", e)
        raise