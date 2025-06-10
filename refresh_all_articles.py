import os
import re
import random
from datetime import datetime, timedelta
from pathlib import Path
from backend.llm import get_llm

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

def process_article(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    frontmatter, content, fm_start, fm_end = extract_frontmatter_and_content(text)
    if not frontmatter:
        print(f"[WARN] No frontmatter in {path}")
        return
    audience, information_type = infer_audience_and_info_type(frontmatter, content)
    llm = get_llm()
    prompt = f"""
    Audience: {audience}
    Information Type: {information_type}
    Aggiorna e migliora leggermente il seguente articolo di blog. 
    Preferisci modifiche minime e leggere, solo dove necessario per chiarezza, aggiornamento o miglioramento dello stile.
    Non cambiare la struttura o il significato del testo se non strettamente necessario. Restituisci solo il nuovo contenuto markdown, senza frontmatter.

        **Istruzioni per l'aggiornamento:**
        Segui queste linee guida per aggiornare e migliorare il contenuto dell'articolo:
        1.  **Scrivi o traduci il testo in italiano:** Mantenendo un tono professionale e accessibile.
        2.  **Grammatica, Sintassi e Ortografia:** Correggi qualsiasi errore grammaticale, di sintassi o ortografico.
        3.  **Chiarezza e Scorrevolezza:** Rendi il testo più chiaro, conciso e scorrevole, eliminando frasi ridondanti o ambigue.
        4.  **Linguaggio:**
            * Evita l'uso di anglicismi inutili o espressioni colloquiali eccessive, preferendo un italiano standard e professionale.
            * Mantieni il tono coerente con quello dell'articolo del blog di Mestieri.pro.
        5.  **Contenuto Sensibile (Competitors):**
            * **NON menzionare in alcun modo piattaforme competitor** come ChronoShare o ProntoPro.
            * Se il contenuto originale dovesse per qualche motivo fare riferimento a tali piattaforme, modifica il testo per rimuovere qualsiasi menzione.
            * In caso sia assolutamente necessario un confronto (sebbene da evitare), riformula il testo in modo da evidenziare sempre e solo i vantaggi e i punti di forza di Mestieri.pro, senza nominare direttamente i competitor.
        6. **Call To Action:** Se il testo originale non include una call to action, aggiungine una alla fine per invitare i lettori a visitare Mestieri.pro, i professionisti a iscriversi, sulla pagina https://mestieri.pro/info o i potenziali clienti a contattare i professionisti del settore su https://mestieri.pro. Includi link diretti nel markdown per questi due URL.
        7. **Chiedi sempre di condividere o lasciare un feedback sull'articolo, per migliorare la qualità dei contenuti.
        8. **Modifiche Minime:** Preferisci modifiche minime e leggere, solo dove necessario per chiarezza, aggiornamento o miglioramento dello stile. Non cambiare la struttura o il significato del testo se non strettamente necessario.

        **Rispondi solo con il contenuto corretto e migliorato, senza aggiungere commenti o preamboli.**

        Contenuto originale da aggiornare:
    {content}
    """
    response = llm.invoke([{"role": "user", "content": prompt}])
    new_content = response.content if hasattr(response, 'content') else str(response)
    new_date = random_date(DATE_START, DATE_END)
    new_frontmatter = update_frontmatter(frontmatter, new_date)
    # Always write frontmatter at the very top
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"---\n{new_frontmatter}\n---\n{new_content}")
    print(f"[OK] Refreshed: {path}")

def main():
    for md_path in BLOG_ROOT.glob("**/*.md"):
        process_article(md_path)

if __name__ == "__main__":
    main()
