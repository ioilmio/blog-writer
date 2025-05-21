# Blog Generator

A local tool that generates blog articles in Italian using AI. Built with React, FastAPI, LangChain, and supports multiple LLM providers (Ollama, Cerebras, Groq).

## Features

- Generate blog articles in Italian from topics
- Retrieval-Augmented Generation (RAG) with Neo4j vector store for context enrichment
- Tag-based article retrieval and enrichment
- Preview generated content before saving
- Save articles in Markdown format, organized in topic-based folders
- Supports multiple LLM providers: Ollama (Deepseek), Cerebras, Groq (configurable via `.env`)
- Efficient, context-aware article generation pipeline

## Prerequisites

Before you begin, ensure you have installed:

- Python 3.8 or higher
- Node.js 18 or higher
- [Ollama](https://ollama.ai/) with the Deepseek model (if using Ollama)
- (Optional) Cerebras or Groq API keys for cloud LLMs
- Docker (for Neo4j vector database)

### Installing Ollama and Deepseek

1. Install Ollama by following the instructions at [ollama.ai](https://ollama.ai)
2. Pull the Deepseek model:
   ```bash
   ollama pull deepseek
   ```

### Setting up Neo4j (Vector Store)

1. Start Neo4j in Docker:
   ```bash
   docker run --name neo4j-blog-rag -d -p7474:7474 -p7687:7687 -v $PWD/neo4j_data:/data -e NEO4J_AUTH=neo4j/testpassword neo4j:latest
   ```

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd blog-generator
   ```

2. Install frontend dependencies:
   ```bash
   pnpm install
   ```

3. Create a Python virtual environment and activate it:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

4. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Configure your `.env` file:
   ```env
   # Example .env
   TAVILY_API_KEY=your-tavily-key
   CEREBRAS_API_KEY=your-cerebras-key
   GROQ_API_KEY=your-groq-key
   LLM_PROVIDER=ollama
   ```
   - Set `LLM_PROVIDER` to `ollama`, `cerebras`, or `groq` as needed.
   - Do not add comments on the same line as variable assignments.

## Running the Application

0. to run automatically use Run All task (ctrl+alt+p -> Task: Run Task -> Run All)

1. Start the Neo4j database (if not already running):
   ```bash
   docker start neo4j-blog-rag
   ```

2. Start the Ollama server (if using Ollama):
   ```bash
   ollama serve
   ```

3. Start the backend server (in a new terminal):
   ```bash
   python -m uvicorn backend.main:app --reload
   ```

4. Start the frontend development server (in another terminal):
   ```bash
   npm run dev
   ```

5. Open your browser and navigate to:
   ```
   http://localhost:5173
   ```

## Project Structure

```
blog-generator/
├── backend/
│   ├── llm/
│   │   └── __init__.py    # LLM configuration, provider selection, and prompts
│   │   └── neo4j_rag.py   # Neo4j vector store integration and RAG logic
│   └── main.py            # FastAPI backend server and workflow
├── src/
│   ├── types/
│   │   └── Article.ts     # TypeScript interfaces
│   ├── App.tsx           # Main React component
│   └── main.tsx          # React entry point
├── package.json          # Frontend dependencies
├── requirements.txt      # Python dependencies
└── README.md
```

## Usage

1. Enter a topic in the input field
2. Add any additional context (optional)
3. Click "Generate Article"
4. Review the generated content
5. Click "Save Article" to save the markdown file

Generated articles will be saved in folders based on their topics:
```
topic-name/
└── article-slug.md
```

## Development

- Frontend: Vite, React, TypeScript, Tailwind CSS
- Backend: FastAPI, LangChain, Neo4j (vector store), multi-provider LLM support
- RAG workflow: Neo4j for enrichment, tag-based retrieval, context-aware LLM calls
- React Hook Form for form handling
- React Markdown for preview rendering

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Esempio articolo

---
title: "Barbieri e Parrucchieri: L'Arte del Taglio e dello Stile"
date: "2025-03-26"
excerpt: "Scopri come i barbieri e i parrucchieri possono migliorare il tuo look e valorizzare la tua immagine con tagli e trattamenti professionali."
slug: "arte-del-taglio"
topic: "Barbieri e Parrucchieri"
tags: ["barbieri", "parrucchieri", "cura dei capelli", "stile", "bellezza"]
---

# Barbieri e Parrucchieri: L'Arte del Taglio e dello Stile

Il mondo dei barbieri e dei parrucchieri è in continua evoluzione, offrendo sempre nuove tecniche e prodotti per migliorare il look e la salute dei capelli. Che si tratti di un semplice taglio, di una colorazione o di un trattamento specifico, questi professionisti sono esperti nel valorizzare ogni tipo di capello.

## Perché Rivolgersi a un Professionista?

Affidarsi a un barbiere o a un parrucchiere qualificato offre numerosi vantaggi:

- **Tagli personalizzati** per adattarsi alla forma del viso e allo stile personale.
- **Trattamenti specifici** per nutrire e proteggere i capelli.
- **Consigli di esperti** per la cura quotidiana del cuoio capelluto e dei capelli.
- **Uso di prodotti professionali** che garantiscono risultati migliori rispetto ai prodotti commerciali.

## Servizi Offerti

I barbieri e i parrucchieri offrono una vasta gamma di servizi, tra cui:

- Taglio e piega
- Colorazione e decolorazione
- Trattamenti per la salute del capello
- Acconciature per eventi speciali
- Consulenze personalizzate per il cambio look

## Come Scegliere il Giusto Professionista

Quando scegli un barbiere o un parrucchiere, considera:

- Le recensioni e il passaparola
- L'esperienza e la formazione del professionista
- L'uso di prodotti di alta qualità
- La capacità di ascoltare le tue esigenze e offrirti consigli mirati

## Conclusione

Un buon taglio di capelli può fare la differenza nel look e nella sicurezza in se stessi. Trovare il professionista giusto significa investire nella propria immagine e nel proprio benessere. Se sei un barbiere o un parrucchiere e vuoi aumentare la tua visibilità, iscriviti a [mestieri.pro](#) e fatti trovare da nuovi clienti!




---
title: "Nail Art in Italia: Tendenze e Novità del Momento"
date: "2025-03-27"
excerpt: "Scopri le ultime tendenze della nail art in Italia, dai colori più richiesti alle tecniche più innovative per unghie sempre alla moda."
slug: "tendenze-nail-art"
topic: "Nail Art e Beauty"
tags: ["nail art", "unghie", "bellezza", "tendenze", "manicure"]
---

# Nail Art in Italia: Tendenze e Novità del Momento

Il mondo della nail art sta vivendo un momento di grande fermento in Italia. Tra nuove tecniche, colori di tendenza e innovazioni nei prodotti, sempre più persone scelgono di curare le proprie unghie con stili personalizzati e originali. Vediamo insieme le principali tendenze del momento.

## I Colori Must-Have per il 2025

La palette di colori per la nail art di quest'anno si ispira alla natura e alla modernità. Ecco alcune delle tonalità più richieste:

- **Toni neutri e lattiginosi**: Perfetti per chi ama uno stile elegante e minimalista.
- **Pastelli soft**: Verde salvia, lilla e celeste sono tra i più apprezzati.
- **Rosso ciliegia e bordeaux**: Ideali per un tocco di classe e raffinatezza.
- **Effetto chrome e metallico**: Per un look futuristico e super trendy.

## Tecniche e Stili in Voga

Le tecniche di nail art si stanno evolvendo con nuove tendenze che conquistano sia professionisti che appassionati. Tra le più popolari troviamo:

- **Baby boomer e french sfumato**: Un grande classico rivisitato in chiave moderna.
- **Unghie jelly e trasparenti**: Look leggero e sofisticato, perfetto per ogni occasione.
- **Micro-design e dettagli minimalisti**: Linee sottili, pois e disegni geometrici per chi ama la discrezione.
- **3D nail art**: Applicazioni in rilievo, pietre e perline per un effetto wow assicurato.

## L'Innovazione nei Prodotti

Il settore della nail art si arricchisce continuamente di nuovi prodotti che migliorano la durata e la resa estetica della manicure. Alcune delle novità più interessanti includono:

- **Gel semipermanenti ultra resistenti**: Fino a 4 settimane di durata senza sbeccature.
- **Smalti vegani e cruelty-free**: Sempre più richiesti da chi cerca alternative sostenibili.
- **Tecnologie di asciugatura rapida**: Per una manicure perfetta in pochi minuti.

## Nail Art per Ogni Occasione

Le unghie non sono solo un dettaglio estetico, ma un vero e proprio accessorio che completa il look. Alcuni esempi di tendenze per diverse occasioni:

- **Per il lavoro**: Unghie corte con colori neutri o un french elegante.
- **Per le feste**: Glitter, dettagli in oro o argento e unghie lunghe a mandorla.
- **Per l'estate**: Colori vivaci, effetti neon e decorazioni tropicali.

## Conclusione

La nail art in Italia continua a evolversi, offrendo a professionisti e appassionati infinite possibilità per esprimere la propria creatività. Che tu sia alla ricerca di un look discreto o di una manicure d'impatto, le tendenze del 2025 hanno qualcosa da offrire a tutti. Se vuoi rimanere sempre aggiornato sulle ultime novità, segui i professionisti del settore e sperimenta le nuove tecniche per unghie sempre perfette!

