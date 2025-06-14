"""
slim_image_inserter.py

Insert high-quality, validated images into article sections.
"""
import sys
import traceback
from pathlib import Path
import yaml

def insert_images_in_article(md_path: str) -> bool:
    """
    Insert images into the markdown article at md_path.
    Returns True if successful, False otherwise.
    """
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        parts = content.split('---')
        if len(parts) < 3:
            print(f"[ERROR] Invalid markdown frontmatter format: {md_path}")
            return False
        frontmatter = yaml.safe_load(parts[1])
        article_body = parts[2].strip()
        # Dummy image insertion: insert a placeholder image after the first H2
        import re
        def insert_after_first_h2(text, image_url):
            return re.sub(r'(## .+?\n)', r'\1![](' + image_url + ')\n', text, count=1, flags=re.DOTALL)
        # In a real implementation, fetch/validate a relevant image here
        image_url = "https://source.unsplash.com/800x400/?" + (frontmatter.get("topic") or "blog")
        new_body = insert_after_first_h2(article_body, image_url)
        # Save the new article
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"---\n{yaml.safe_dump(frontmatter)}---\n{new_body}")
        print(f"[OK] Image inserted in: {md_path}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to insert image in {md_path}: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Example usage
    md_path = "blog-post/dj/dj-clienti-in-cerca-di-servizi-guida-pratica.md"
    insert_images_in_article(md_path)
