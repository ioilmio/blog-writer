from langchain.llms import Ollama
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

# Initialize Ollama with Deepseek model
llm = Ollama(model="deepseek")

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
    # Generate the prompt
    _prompt = prompt.format(topic=topic, additional_context=additional_context)
    
    # Get response from LLM
    response = await llm.agenerate([_prompt])
    
    # Parse the response
    article = parser.parse(response.generations[0].text)
    
    return article