#!/usr/bin/env python3
"""
run_full_pipeline.py

Master script to run the full blog workflow (generation, refresh, image insertion) with step control and service checks.
"""
import subprocess
import sys
import argparse
import os
from pathlib import Path

def check_service(name, check_cmd, start_task=None):
    try:
        result = subprocess.run(check_cmd, shell=True, capture_output=True)
        if result.returncode == 0:
            print(f"[OK] {name} is running.")
            return True
        else:
            print(f"[INFO] {name} not running. Starting...")
            if start_task:
                # Start FastAPI directly in the background if requested
                if name == "FastAPI Backend":
                    subprocess.Popen(["uvicorn", "backend.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    print(f"[OK] {name} started (direct uvicorn call).")
                    return True
                else:
                    subprocess.run(start_task, shell=True)
                    print(f"[OK] {name} started.")
                    return True
            else:
                print(f"[WARN] No start command for {name}.")
                return False
    except Exception as e:
        print(f"[ERROR] Checking/starting {name}: {e}")
        return False

def get_test_articles():
    # Hardcoded test set: category, audience, information_type
    # Each tuple: (category, audience, information_type)
    categories = [
        ("dj",),
        ("fabbri",),
        ("estetisti",),
        ("doposcuola",),
    ]
    audiences = ["clienti in cerca di servizi", "professionisti del settore"]
    info_types = ["guida pratica", "strategie e tendenze"]
    # Build all combinations
    test_cases = []
    for cat_tuple in categories:
        cat = cat_tuple[0]
        for audience in audiences:
            for info_type in info_types:
                test_cases.append((cat, audience, info_type))
    return test_cases

def upsert_all_articles_to_neo4j(files=None):
    from backend.llm.neo4j_rag import upsert_article_in_neo4j
    import yaml
    from pathlib import Path
    blog_dir = Path("blog-post")
    if files is None:
        files = list(blog_dir.glob("**/*.md"))
    for md_file in files:
        with open(md_file, "r", encoding="utf-8") as f:
            lines = f.read().split('---')
            if len(lines) < 3:
                continue
            frontmatter = yaml.safe_load(lines[1])
            content = lines[2].strip()
            article = dict(frontmatter)
            article["content"] = content
            upsert_article_in_neo4j(article)

def step_generate():
    print("[STEP] Blog post generation and Neo4j sync...")
    test_cases = get_test_articles()
    from generate_all_blog_posts import generate_and_save_article
    generated_files = []
    for cat, audience, info_type in test_cases:
        # Compose topic and output path
        topic = f"{cat.title()} - {info_type}"
        output_path = f"blog-post/{cat}/{cat}-{audience.replace(' ', '-')}-{info_type.replace(' ', '-')}.md"
        # Map audience string to booleans
        if audience == "clienti in cerca di servizi":
            customer_audience = True
            professional_copy = False
        else:
            customer_audience = False
            professional_copy = True
        additional_context = ""
        # Send professional_copy as string for FastAPI compatibility
        generate_and_save_article(
            topic,
            additional_context,
            customer_audience,
            info_type,
            output_path,
            str(professional_copy).lower()  # 'true' or 'false' as string
        )
        generated_files.append(Path(output_path))
    upsert_all_articles_to_neo4j(generated_files)
    print("[STEP] All generated articles upserted to Neo4j.")

def step_refresh():
    print("[STEP] Refreshing articles and Neo4j sync...")
    test_cases = get_test_articles()
    files = []
    for cat, audience, info_type in test_cases:
        path = Path(f"blog-post/{cat}/{cat}-{audience.replace(' ', '-')}-{info_type.replace(' ', '-')}.md")
        if path.exists():
            files.append(path)
    result = subprocess.run([sys.executable, "refresh_all_articles.py"] + [str(f) for f in files])
    if result.returncode != 0:
        print("[ERROR] Article refresh failed.")
        sys.exit(1)
    upsert_all_articles_to_neo4j(files)
    print("[STEP] All refreshed articles upserted to Neo4j.")

def step_images():
    print("[STEP] Fetching and inserting images...")
    test_cases = get_test_articles()
    files = []
    for cat, audience, info_type in test_cases:
        path = Path(f"blog-post/{cat}/{cat}-{audience.replace(' ', '-')}-{info_type.replace(' ', '-')}.md")
        if path.exists():
            files.append(path)
    result = subprocess.run([sys.executable, "fetch_and_insert_images.py"] + [str(f) for f in files])
    if result.returncode != 0:
        print("[ERROR] Image fetch/insertion failed.")
        sys.exit(1)
    upsert_all_articles_to_neo4j(files)
    print("[STEP] All articles with images upserted to Neo4j.")

def main():
    parser = argparse.ArgumentParser(description="Run the full blog pipeline with step control.")
    parser.add_argument("--start-from", choices=["generate", "refresh", "images"], default="generate", help="Step to start from.")
    parser.add_argument("--force", action="store_true", help="Force rerun all steps, even if outputs exist.")
    args = parser.parse_args()

    # Service checks (Ollama, FastAPI, Neo4j)
    check_service("Ollama", "pgrep -f 'ollama serve'", "code --task 'Ollama Serve'")
    check_service("FastAPI Backend", "pgrep -f 'uvicorn backend.main:app'", "code --task 'FastAPI Backend'")
    check_service("Neo4j", "docker ps -q -f name=neo4j-blog-rag", "code --task 'Neo4j Database'")

    steps = ["generate", "refresh", "images"]
    start_idx = steps.index(args.start_from)
    for step in steps[start_idx:]:
        if step == "generate":
            # Skip if blog-post/ is not empty and not --force
            if not args.force and any(Path("blog-post").glob("**/*.md")):
                print("[SKIP] Blog posts already exist. Use --force to regenerate.")
            else:
                step_generate()
        elif step == "refresh":
            # Skip if already refreshed and not --force
            dev_posts = Path(os.path.expanduser("~/quadro/mestieri/dev-posts"))
            if not args.force and dev_posts.exists() and any(dev_posts.glob("**/*.md")):
                print("[SKIP] Articles already refreshed. Use --force to rerun.")
            else:
                step_refresh()
        elif step == "images":
            # Skip if images already exist and not --force
            public_dir = Path(os.path.expanduser("~/quadro/mestieri/public"))
            if not args.force and public_dir.exists() and any(public_dir.glob("**/*.jpg")):
                print("[SKIP] Images already exist. Use --force to rerun.")
            else:
                step_images()

if __name__ == "__main__":
    main()