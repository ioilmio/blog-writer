"""
slim_pipeline.py

A streamlined pipeline for blog article generation, image insertion, and Neo4j upsert.
"""
import sys
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any
from generate_all_blog_posts import generate_and_save_article
import yaml
import random
from slim_image_inserter import insert_images_in_article
from slim_neo4j_upsert import upsert_article_from_md

# --- Step 1: Generate and validate article ---
def generate_article_with_metadata(topic: str, audience: str, info_type: str, output_path: str) -> Dict[str, Any]:
    """
    Generate a high-quality article with all required metadata and validate the result.
    Returns the article as a dict if successful, raises Exception otherwise.
    """
    # Generate a random date within the last 90 days
    today = datetime.now()
    random_days = random.randint(0, 90)
    article_date = (today - timedelta(days=random_days)).strftime("%Y-%m-%d")
    # Compose additional context (add more as needed)
    additional_context = f"Random date: {article_date}"
    # Map audience to booleans for compatibility
    customer_audience = audience == "clienti in cerca di servizi"
    professional_copy = not customer_audience
    # Generate article
    try:
        generate_and_save_article(
            topic,
            additional_context,
            customer_audience,
            info_type,
            output_path,
            str(professional_copy).lower()
        )
        # Validate output
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
        parts = content.split('---')
        if len(parts) < 3:
            raise ValueError("Invalid markdown frontmatter format.")
        frontmatter = yaml.safe_load(parts[1])
        required_fields = ["title", "date", "excerpt", "slug", "topic", "tags"]
        for field in required_fields:
            if field not in frontmatter:
                raise ValueError(f"Missing required field: {field}")
        if not parts[2].strip():
            raise ValueError("Article content is empty.")
        print(f"[OK] Article generated and validated: {output_path}")
        return {**frontmatter, "content": parts[2].strip()}
    except Exception as e:
        print(f"[ERROR] Failed to generate/validate article for {topic}: {e}")
        traceback.print_exc()
        raise

def get_test_articles():
    categories = ["dj", "fabbri", "estetisti", "doposcuola"]
    audiences = ["clienti in cerca di servizi", "professionisti del settore"]
    info_types = ["guida pratica", "strategie e tendenze"]
    test_cases = []
    for cat in categories:
        for audience in audiences:
            for info_type in info_types:
                test_cases.append((cat, audience, info_type))
    return test_cases

# Next: add image insertion and Neo4j upsert steps

if __name__ == "__main__":
    results = []
    for cat, audience, info_type in get_test_articles():
        topic = f"{cat.title()} - {info_type}"
        output_path = f"blog-post/{cat}/{cat}-{audience.replace(' ', '-')}-{info_type.replace(' ', '-')}.md"
        Path(f"blog-post/{cat}").mkdir(parents=True, exist_ok=True)
        try:
            article = generate_article_with_metadata(topic, audience, info_type, output_path)
            img_ok = insert_images_in_article(output_path)
            upsert_ok = upsert_article_from_md(output_path) if img_ok else False
            results.append((output_path, True, img_ok, upsert_ok))
        except Exception as e:
            results.append((output_path, False, False, False))
    print("\n--- Pipeline Summary ---")
    for path, gen_ok, img_ok, upsert_ok in results:
        print(f"{path}: gen={'OK' if gen_ok else 'FAIL'}, img={'OK' if img_ok else 'FAIL'}, upsert={'OK' if upsert_ok else 'FAIL'}")
