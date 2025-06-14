from langchain_ollama import ChatOllama
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List
import json
from langchain_cerebras import ChatCerebras
from langchain_groq import ChatGroq
import os
import re

class BlogArticle(BaseModel):
    title: str = Field(description="The title of the blog article")
    excerpt: str = Field(description="A brief summary of the article")
    tags: List[str] = Field(description="List of relevant tags for the article")
    content: str = Field(description="The main content of the article in markdown format")

# Select LLM provider based on environment variable
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").strip().lower().replace('"', '').replace("'", "")  # 'ollama' or 'cerebras' or 'groq'

# Read Cerebras API key from environment
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Factory for LLM

def get_llm():
    if LLM_PROVIDER == "cerebras":
        if not CEREBRAS_API_KEY:
            raise ValueError("CEREBRAS_API_KEY is not set in environment.")
        return ChatCerebras(api_key=CEREBRAS_API_KEY, model="llama-4-scout-17b-16e-instruct", temperature=0.5)
    elif LLM_PROVIDER == "groq":
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set in environment.")
        return ChatGroq(api_key=GROQ_API_KEY, model="meta-llama/llama-4-scout-17b-16e-instruct", temperature=0.5)
    else:
        return ChatOllama(model="llama3.1:latest", temperature=0.5)

# Use the LLM factory for all LLM calls
llm = get_llm()
# Template for generating blog articles
BLOG_TEMPLATE = """
IMPORTANTE: Rispondi SOLO con un oggetto JSON valido che rispetta lo schema fornito. Niente markdown, niente spiegazioni, niente testo extra. Solo JSON.\n
Scrivi un articolo di blog in italiano, altamente informativo e accattivante, per il mercato e il pubblico italiano sull'argomento: \"{topic}\".

Audience: {audience}

Obiettivo: Fornire informazioni utili e pratiche al pubblico di {audience} per aiutarli a comprendere meglio il servizio/mestiere e a fare scelte informate o a migliorare la loro attività.

Lunghezza: Circa 1000-1100 parole (3-4 minuti di lettura).

Tono e Stile: Adotta un tono professionale ma accessibile, chiaro e coinvolgente.
* Se l'audience è \"consumatori interessati a trovare o capire meglio i servizi offerti dai professionisti.\": Il tono dovrà essere rassicurante e orientato a spiegare i benefici del servizio e come scegliere il professionista giusto. Evita tecnicismi e usa un linguaggio semplice.
* Se l'audience è \"professionisti del settore che vogliono tenersi aggiornati.\": Il tono dovrà essere pratico, orientato a fornire strategie, consigli per la crescita del business o miglioramento delle competenze. Possono essere usati termini più specifici del settore, ma sempre spiegati o contestualizzati se necessario.

Formato dell'Articolo (Output): L'articolo finale deve essere formattato interamente in Markdown. Utilizza:
* Un titolo principale (H1)
* Sottotitoli (H2, H3) per organizzare le sezioni.
* Paragrafi chiari e concisi.
* Liste puntate o numerate dove appropriato per facilitare la lettura.

Struttura dell'articolo:

# Titolo Accattivante dell'Articolo (H1)
(Crea un titolo H1 che sia pertinente all'argomento, accattivante e ottimizzato per il pubblico specifico. Ad esempio, per i consumatori: \"Come scegliere il Miglior Parrucchiere a [Città]\" o per i professionisti: \"Strategie Vincenti per Barbieri e Parrucchieri Indipendenti\")

* Introduzione (Paragrafo): Cattura l'attenzione del lettore, presenta brevemente l'argomento e il problema/bisogno che l'articolo intende risolvere per il tuo specifico pubblico.
* Corpo dell'articolo (Sezioni con sottotitoli H2/H3 e paragrafi):
    * Spiega l'argomento in modo chiaro e dettagliato.
    * Per i consumatori: Evidenzia i benefici di affidarsi a un professionista qualificato in questo settore. Fornisci consigli pratici su \"Quando è il momento di X?\", \"Cosa cercare in un buon Y?\", \"Come si svolge il servizio Z?\". Se pertinente, accenna a fattori che influenzano i costi o a come richiedere un preventivo (senza inserire cifre precise se non di contesto generale).
    * Per i professionisti: Offri strategie, best practice, consigli per ottimizzare il lavoro, trovare clienti (in linea con la filosofia di Mestieri.pro), gestire l'attività o migliorare le competenze.
    * Includi, se pertinente, una piccola sezione \"Domande Frequenti (FAQ)\" relative all'argomento per il pubblico di riferimento.
* Conclusione (Paragrafo): Riassumi brevemente i punti chiave discussi. Rafforza l'importanza del servizio/mestiere e, per entrambi i pubblici, invita il lettore a visitare Mestieri.pro per connettersi con professionisti qualificati (se cliente) o per trovare nuove opportunità di lavoro (se professionista), enfatizzando i vantaggi della piattaforma (basse commissioni per i professionisti, contatti diretti, pubblicazione offerte, app mobile etc.).

Contesto aggiuntivo per l'articolo: {additional_context}
(Questo contesto includerà il riassunto dei risultati di ricerca web e, se implementato, il tipo di informazione specifica per l'articolo per un contesto più ricco.)

Correggi eventuali typos, errori di sintassi o grammaticali, non usare inglesismi inutili.
Non menzionare altre piattaforme come ChronoShare o ProntoPro che sono competitor di Mestieri.pro.Se devi menzionarle sii sempre in favore di Mestieri.pro nella comparazione.

{format_instructions}
"""

# Helper to extract first JSON object from a string
def extract_json(text):
    match = re.search(r'{.*}', text, re.DOTALL)
    if match:
        try:
            return match.group(0)
        except Exception:
            pass
    return text

# Initialize the parser
parser = PydanticOutputParser(pydantic_object=BlogArticle)

# Create the prompt template
prompt = PromptTemplate(
    template=BLOG_TEMPLATE,
    input_variables=["topic", "additional_context", "audience"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

async def generate_article(topic: str, additional_context: str = "", audience: str = "") -> BlogArticle:
    try:
        _prompt = prompt.format(topic=topic, additional_context=additional_context, audience=audience)
        response = await llm.ainvoke([
            {"role": "user", "content": _prompt}
        ])
        print("[LLM] response article.", response)
        # Extract JSON if extra text is present
        json_text = extract_json(response.content)
        article = parser.parse(json_text)
        print("[LLM] parsed article.", article)
        return article
    except Exception as e:
        print("LLM error:", e)
        raise