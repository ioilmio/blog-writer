import os
import re
import random
from datetime import datetime, timedelta
from pathlib import Path
from backend.llm import get_llm
import yaml

# --- CONFIG ---
BLOG_ROOT = Path("blog-post")
DATE_START = datetime(2024, 12, 17)
DATE_END = datetime(2025, 6, 8)

# --- HELPERS ---
def random_date(start, end):
    """Return a random date between start and end (datetime objects)."""
    delta = end - start
    random_days = random.randint(0, delta.days)
    return (start + timedelta(days=random_days)).strftime("%Y-%m-%d")

def extract_frontmatter_and_content(text):
    # Skip leading blank lines and comments
    lines = text.splitlines()
    i = 0
    while i < len(lines) and (lines[i].strip() == '' or lines[i].strip().startswith('<!--')):
        i += 1
    if i < len(lines) and lines[i].strip() == '---':
        # Find end of frontmatter
        start = i
        end = start + 1
        while end < len(lines) and lines[end].strip() != '---':
            end += 1
        if end < len(lines):
            frontmatter = '\n'.join(lines[start+1:end])
            content = '\n'.join(lines[end+1:])
            return frontmatter, content, start, end
    return None, text, None, None

def extract_audience_from_frontmatter(frontmatter):
    # Try to extract an 'audience' or similar field from the frontmatter
    for line in frontmatter.splitlines():
        if line.strip().startswith('audience:'):
            return line.split(':', 1)[1].strip().strip('"\'')
    # Fallback: try to infer from topic or tags
    return None

def extract_information_type_from_frontmatter(frontmatter):
    for line in frontmatter.splitlines():
        if line.strip().startswith('information_type:'):
            return line.split(':', 1)[1].strip().strip('"\'')
    return None

def update_frontmatter(frontmatter, new_date):
    lines = frontmatter.splitlines()
    new_lines = []
    found_date = False
    for line in lines:
        if line.strip().startswith("date:"):
            new_lines.append(f'date: "{new_date}"')
            found_date = True
        else:
            new_lines.append(line)
    if not found_date:
        new_lines.append(f'date: "{new_date}"')
    return "\n".join(new_lines)

def infer_audience_and_info_type(frontmatter, content):
    # Try to infer audience from topic/tags/content
    fm_lower = frontmatter.lower()
    content_lower = content.lower()
    if any(word in fm_lower or word in content_lower for word in ["professionista", "professionale", "business", "lavoro", "consigli per professionisti", "clienti", "attività", "guadagni", "strategie per professionisti"]):
        audience = "professionisti del settore"
    else:
        audience = "clienti in cerca di servizi"
    # Infer information_type from topic/tags/content
    if any(word in fm_lower or word in content_lower for word in ["guida", "come scegliere", "consigli", "faq", "domande frequenti"]):
        information_type = "guida pratica"
    elif any(word in fm_lower or word in content_lower for word in ["strategie", "tendenze", "trend", "novità"]):
        information_type = "strategie e tendenze"
    else:
        information_type = ""
    return audience, information_type

def parse_yaml_frontmatter(fm_text):
    try:
        return yaml.safe_load(fm_text)
    except Exception:
        return {}

def dump_yaml_frontmatter(fm_dict):
    # Always dump as block style, no nulls
    return yaml.dump(fm_dict, allow_unicode=True, default_flow_style=False, sort_keys=False).strip()

def process_article(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    frontmatter, content, fm_start, fm_end = extract_frontmatter_and_content(text)
    if not frontmatter:
        print(f"[WARN] No frontmatter in {path}")
        return
    orig_fm_dict = parse_yaml_frontmatter(frontmatter)
    audience, information_type = infer_audience_and_info_type(frontmatter, content)
    llm = get_llm()
    prompt = f"""
    Audience: {audience}
    Information Type: {information_type}
    Aggiorna e migliora leggermente il seguente articolo di blog.
    Preferisci modifiche minime e leggere, solo dove necessario per chiarezza, aggiornamento o miglioramento dello stile.
    Non cambiare la struttura o il significato del testo se non strettamente necessario.

    Oltre a migliorare il contenuto, aggiorna la frontmatter come segue:
    - Aggiorna la data a una data recente random tra {DATE_START.date()} e {DATE_END.date()}.
    - Genera una lista di 5-10 tag ottimizzati per la SEO (brevi, rilevanti, in italiano, come parole chiave, array YAML) per il campo tags.
    - Genera una lista separata di 5-10 image_tags (array YAML): concetti visivi, oggetti o scene rilevanti per l'articolo, adatti come query per la ricerca di immagini stock, che riflettano i temi, le azioni e gli elementi visivi principali dell'articolo e delle sue sezioni.
    - Mantieni tutti gli altri campi della frontmatter invariati.
    - Restituisci la nuova frontmatter completa (in cima, tra ---), seguita dal contenuto markdown aggiornato.

    Esempi:
    ---
    title: Come trovare il miglior dog sitter
    ...
    tags:
      - dog sitter
      - cura animali
      - servizi per animali
      - passeggiata con il cane
      - animali domestici
    image_tags:
      - cane felice
      - passeggiata cane
      - pet sitter
      - guinzaglio
      - parco per cani
    ---
    ...

    ---
    title: Strategie per una ristrutturazione di successo
    ...
    tags:
      - ristrutturazione casa
      - lavori edili
      - progettazione interni
      - edilizia
      - consigli casa
    image_tags:
      - cantiere edile
      - strumenti da lavoro
      - casa ristrutturata
      - architetto
      - progetto edilizio
    ---
    ...

    **Istruzioni per l'aggiornamento:**
    1. Scrivi o traduci il testo in italiano, mantenendo un tono professionale e accessibile.
    2. Correggi errori grammaticali, di sintassi o ortografici.
    3. Rendi il testo più chiaro, conciso e scorrevole.
    4. Evita anglicismi inutili, mantieni un tono coerente con il blog di Mestieri.pro.
    5. NON menzionare piattaforme competitor come ChronoShare o ProntoPro.
    6. Se manca, aggiungi una call to action e una richiesta di feedback alla fine.
    7. Preferisci modifiche minime e leggere.

    Rispondi solo con la nuova frontmatter e il contenuto markdown aggiornato, senza commenti o preamboli.

    Contenuto originale da aggiornare:
{content}
    """
    response = llm.invoke([{"role": "user", "content": prompt}])
    new_text = response.content if hasattr(response, 'content') else str(response)
    # Try to extract new frontmatter and content
    new_fm, new_content, _, _ = extract_frontmatter_and_content(new_text)
    if not new_fm:
        print(f"[WARN] LLM did not return valid frontmatter for {path}, skipping.")
        return
    # Parse new tags and image_tags from LLM output
    new_fm_dict = parse_yaml_frontmatter(new_fm)
    # Always preserve all original fields and types
    merged_fm = orig_fm_dict.copy()
    # Update date if present in new frontmatter, else keep original
    if 'date' in new_fm_dict:
        merged_fm['date'] = str(new_fm_dict['date'])
    # Update tags as array if present
    if 'tags' in new_fm_dict:
        tags = new_fm_dict['tags']
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',') if t.strip()]
        merged_fm['tags'] = tags
    # Update image_tags as array if present
    if 'image_tags' in new_fm_dict:
        image_tags = new_fm_dict['image_tags']
        if isinstance(image_tags, str):
            image_tags = [t.strip() for t in image_tags.split(',') if t.strip()]
        merged_fm['image_tags'] = image_tags
    # Dump merged frontmatter as YAML
    merged_fm_yaml = dump_yaml_frontmatter(merged_fm)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"---\n{merged_fm_yaml}\n---\n{new_content}")
    print(f"[OK] Refreshed: {path}")

def main():
    # Only process the first 4 markdown files in muratori/ for testing
    test_files = list(Path("blog-post/muratori").glob("*.md"))[:4]
    for md_path in test_files:
        process_article(md_path)

if __name__ == "__main__":
    main()
