import Fastify from 'fastify';
import cors from '@fastify/cors';
import { writeFile, mkdir } from 'node:fs/promises';
import { dirname } from 'node:path';
import { ChatOllama } from 'langchain/ChatOllama';
import { PromptTemplate } from 'langchain/prompts';
import slugify from 'slugify';

const fastify = Fastify({
  logger: true
});

await fastify.register(cors, {
  origin: 'http://localhost:5173'
});

// Initialize Ollama with Deepseek model
const llm = new ChatOllama({
  baseUrl: 'http://localhost:11434',
  model: 'deepseek-r1:14b'
});

// Template for generating blog articles
const BLOG_TEMPLATE = `
Scrivi un articolo di blog in italiano sul seguente argomento: {topic}
L'articolo deve essere informativo e piacevole da leggere in 2-3 minuti circa 60-700 parole.
L'articolo si rivolge aun pubblico di consumatori interessati all'argomento, quindi evita tecnicismi e termini troppo specialistici.
Contesto aggiuntivo: {additionalContext}

L'articolo deve seguire questo formato:
1. Un titolo accattivante
2. Un breve estratto che riassume l'articolo
3. Tag pertinenti
4. Contenuto principale in formato markdown

L'output deve essere in formato JSON con i seguenti campi:
{
  "title": "Il titolo dell'articolo",
  "excerpt": "Un breve riassunto",
  "tags": ["tag1", "tag2", "tag3"],
  "content": "Il contenuto in markdown"
}
Ecco un esempio di articolo:

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


`;

const prompt = new PromptTemplate({
  template: BLOG_TEMPLATE,
  inputVariables: ['topic', 'additionalContext']
});

fastify.post('/api/generate', async (request, reply) => {
  try {
    const { topic, additionalContext = '' } = request.body;
    
    const formattedPrompt = await prompt.format({
      topic,
      additionalContext
    });
    console.log(formattedPrompt);
    
    
    const response = await llm.call(formattedPrompt);
    console.log(response);
    
    const article = JSON.parse(response);
    
    const now = new Date().toISOString().split('T')[0];
    const slug = slugify(article.title, { lower: true });
    
    return {
      ...article,
      date: now,
      slug,
      topic
    };
  } catch (error) {
    reply.code(500).send({ error: error.message });
  }
});

fastify.post('/api/save', async (request, reply) => {
  try {
    const article = request.body;
    const topicDir = slugify(article.topic, { lower: true });
    const filePath = `${topicDir}/${article.slug}.md`;
    
    // Create markdown content
    const markdown = `---
title: "${article.title}"
date: "${article.date}"
excerpt: "${article.excerpt}"
slug: "${article.slug}"
topic: "${article.topic}"
tags: ${JSON.stringify(article.tags)}
---

${article.content}`;
    
    // Create directory if it doesn't exist
    await mkdir(topicDir, { recursive: true });
    
    // Save the file
    await writeFile(filePath, markdown, 'utf-8');
    
    return { message: 'Article saved successfully', path: filePath };
  } catch (error) {
    reply.code(500).send({ error: error.message });
  }
});

try {
  await fastify.listen({ port: 8000 });
  console.log('Server running at http://localhost:8000');
} catch (err) {
  fastify.log.error(err);
  process.exit(1);
}