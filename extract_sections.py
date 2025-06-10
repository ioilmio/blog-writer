import re
from pathlib import Path

# --- CONFIG ---
BLOG_ROOT = Path("blog-post")

# --- HELPERS ---
def extract_sections_from_markdown(md_text):
    """
    Extract (section_title, section_text) pairs for each H2/H3 section in the markdown.
    Returns a list of tuples: (title, text)
    """
    sections = []
    current_title = None
    current_text = []
    for line in md_text.splitlines():
        h2 = re.match(r"^##+\s+(.*)", line)
        if h2:
            if current_title:
                sections.append((current_title, "\n".join(current_text).strip()))
            current_title = h2.group(1).strip()
            current_text = []
        elif current_title:
            current_text.append(line)
    if current_title:
        sections.append((current_title, "\n".join(current_text).strip()))
    return sections

def main():
    for md_path in BLOG_ROOT.glob("**/*.md"):
        with open(md_path, "r", encoding="utf-8") as f:
            text = f.read()
        sections = extract_sections_from_markdown(text)
        print(f"\nFile: {md_path}")
        for i, (title, content) in enumerate(sections, 1):
            print(f"  Section {i}: {title}")
            # Optionally print content or just the title

if __name__ == "__main__":
    main()
