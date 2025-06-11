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
                subprocess.run(start_task, shell=True)
                print(f"[OK] {name} started.")
                return True
            else:
                print(f"[WARN] No start command for {name}.")
                return False
    except Exception as e:
        print(f"[ERROR] Checking/starting {name}: {e}")
        return False

def step_generate():
    print("[STEP] Blog post generation...")
    result = subprocess.run([sys.executable, "generate_all_blog_posts.py"])
    if result.returncode != 0:
        print("[ERROR] Blog post generation failed.")
        sys.exit(1)

def step_refresh():
    print("[STEP] Refreshing articles...")
    result = subprocess.run([sys.executable, "refresh_all_articles.py"])
    if result.returncode != 0:
        print("[ERROR] Article refresh failed.")
        sys.exit(1)

def step_images():
    print("[STEP] Fetching and inserting images...")
    result = subprocess.run([sys.executable, "fetch_and_insert_images.py"])
    if result.returncode != 0:
        print("[ERROR] Image fetch/insertion failed.")
        sys.exit(1)

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
