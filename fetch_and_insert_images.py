import os
import re
import requests
from pathlib import Path
import yaml
from urllib.parse import quote
import torch
import clip
from PIL import Image
import json

# --- CONFIG ---
ARTICLE_ROOT = Path("blog-post")
OUTPUT_ARTICLE_ROOT = Path(os.path.expanduser("~/quadro/mestieri/dev-posts"))
OUTPUT_IMAGE_ROOT = Path(os.path.expanduser("~/quadro/mestieri/public"))
UNSPLASH_KEY = "2PO5W5bjDSuq1ISHYsP9WNuLWctqHxZb33bOdi6ZOzQ"
PEXELS_KEY = "563492ad6f917000010000011093a5f01ff04840900a4ff5ca8ad7cd"
HEADERS_PEXELS = {"Authorization": PEXELS_KEY}
CLIP_THRESHOLD = 0.30

# Load CLIP model once
clip_device = "cuda" if torch.cuda.is_available() else "cpu"
clip_model, clip_preprocess = clip.load("ViT-B/32", device=clip_device)

# --- HELPERS ---
def extract_frontmatter_and_content(text):
    lines = text.splitlines()
    i = 0
    while i < len(lines) and (lines[i].strip() == '' or lines[i].strip().startswith('<!--')):
        i += 1
    if i < len(lines) and lines[i].strip() == '---':
        start = i
        end = start + 1
        while end < len(lines) and lines[end].strip() != '---':
            end += 1
        if end < len(lines):
            frontmatter = '\n'.join(lines[start+1:end])
            content = '\n'.join(lines[end+1:])
            return frontmatter, content
    return None, text

def parse_yaml_frontmatter(fm_text):
    try:
        return yaml.safe_load(fm_text)
    except Exception:
        return {}

def extract_sections_from_markdown(md_text):
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

def fetch_unsplash_image(query):
    print(f"[UNSPLASH] Query: {query}")
    url = f"https://api.unsplash.com/search/photos?query={quote(query)}&orientation=squarish&per_page=5"
    resp = requests.get(url, headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"})
    print(f"[UNSPLASH] Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"[UNSPLASH] Results: {len(data.get('results', []))}")
        for img in data.get("results", []):
            if img.get("urls", {}).get("small"):
                print(f"[UNSPLASH] Found image: {img['urls']['small']}")
                return img["urls"]["small"], img["alt_description"] or query
    else:
        print(f"[UNSPLASH] Error: {resp.text}")
    return None, None

def fetch_pexels_image(query):
    print(f"[PEXELS] Query: {query}")
    url = f"https://api.pexels.com/v1/search?query={quote(query)}&orientation=square&per_page=5"
    resp = requests.get(url, headers=HEADERS_PEXELS)
    print(f"[PEXELS] Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"[PEXELS] Results: {len(data.get('photos', []))}")
        for img in data.get("photos", []):
            if img.get("src", {}).get("medium"):
                print(f"[PEXELS] Found image: {img['src']['medium']}")
                return img["src"]["medium"], img.get("alt", query)
    else:
        print(f"[PEXELS] Error: {resp.text}")
    return None, None

def download_image(url, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
    print(f"[DOWNLOAD] Downloading: {url} -> {out_path}")
    resp = requests.get(url)
    if resp.status_code == 200:
        with open(out_path, "wb") as f:
            f.write(resp.content)
        print(f"[DOWNLOAD] Success: {out_path}")
        return True
    print(f"[DOWNLOAD] Failed: {url} (status {resp.status_code})")
    return False

def slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\-\s]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-")

def insert_images_in_markdown(md_text, section_to_img):
    lines = md_text.splitlines()
    out_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        h2 = re.match(r"^##+\s+(.*)", line)
        if h2 and h2.group(1).strip() in section_to_img:
            out_lines.append(line)
            img_url, alt = section_to_img[h2.group(1).strip()]
            out_lines.append(f"![{alt}]({img_url})")
        else:
            out_lines.append(line)
        i += 1
    return "\n".join(out_lines)

def clip_score(img_path, query):
    pil_image = Image.open(img_path)
    tensor = clip_preprocess(pil_image)
    if isinstance(tensor, torch.Tensor):
        tensor = tensor.unsqueeze(0).to(clip_device)
    else:
        return 0.0
    text = clip.tokenize([query]).to(clip_device)
    with torch.no_grad():
        image_features = clip_model.encode_image(tensor)
        text_features = clip_model.encode_text(text)
        image_features /= image_features.norm(dim=-1, keepdim=True)
        text_features /= text_features.norm(dim=-1, keepdim=True)
        similarity = (image_features @ text_features.T).item()
    return similarity

def process_article(md_path, out_article_dir, out_image_dir):
    print(f"[PROCESS] Article: {md_path}")
    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()
    frontmatter, content = extract_frontmatter_and_content(text)
    if not frontmatter:
        print(f"[PROCESS] No frontmatter found in {md_path}")
        return
    fm = parse_yaml_frontmatter(frontmatter)
    image_tags = fm.get("image_tags", [])
    print(f"[PROCESS] image_tags: {image_tags}")
    slug = fm.get("slug") or slugify(fm.get("title", ""))
    print(f"[PROCESS] slug: {slug}")
    sections = extract_sections_from_markdown(content)
    print(f"[PROCESS] Sections found: {len(sections)}")
    section_to_img = {}
    used_queries = set()
    img_count = 0
    # Image cache directory for rejected images
    image_cache_dir = out_image_dir.parent / "_image_cache"
    image_cache_dir.mkdir(parents=True, exist_ok=True)
    for title, section_text in sections:
        if img_count >= 2:
            break
        print(f"[PROCESS] Section: {title}")
        queries = [title] + image_tags
        for q in queries:
            if q in used_queries:
                continue
            used_queries.add(q)
            img_filename = f"{slug}-{slugify(title)}.jpg"
            img_path = out_image_dir / img_filename
            cache_path = image_cache_dir / img_filename
            # Check cache first
            if cache_path.exists():
                print(f"[CACHE] Found cached image for '{q}': {cache_path}")
                score = clip_score(cache_path, q)
                print(f"[CLIP] (CACHE) {img_filename} <-> '{q}' score: {score:.4f}")
                if score >= CLIP_THRESHOLD:
                    # Copy from cache to output dir
                    cache_path.replace(img_path)
                    section_to_img[title] = (f"/public/{out_image_dir.name}/{img_filename}", q)
                    img_count += 1
                    print(f"[PROCESS] Image ACCEPTED from cache for section '{title}': {img_filename}")
                    break
                else:
                    print(f"[PROCESS] Cached image still not valid for section '{title}': {img_filename}")
                    continue
            # If not in cache, fetch from API
            img_url, alt = fetch_unsplash_image(q)
            if not img_url:
                img_url, alt = fetch_pexels_image(q)
            if img_url:
                if download_image(img_url, img_path):
                    score = clip_score(img_path, q)
                    print(f"[CLIP] {img_filename} <-> '{q}' score: {score:.4f}")
                    if score >= CLIP_THRESHOLD:
                        section_to_img[title] = (f"/public/{out_image_dir.name}/{img_filename}", alt)
                        img_count += 1
                        print(f"[PROCESS] Image ACCEPTED for section '{title}': {img_filename}")
                        break
                    else:
                        print(f"[PROCESS] Image REJECTED for section '{title}': {img_filename}")
                        # Move rejected image to cache instead of deleting
                        img_path.replace(cache_path)
                        print(f"[CACHE] Moved rejected image to: {cache_path}")
    print(f"[PROCESS] Total images assigned: {img_count}")
    new_content = insert_images_in_markdown(content, section_to_img)
    out_article_dir.mkdir(parents=True, exist_ok=True)
    out_image_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_article_dir / md_path.name
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"---\n{frontmatter}\n---\n{new_content}")
    print(f"[OK] {md_path} -> {out_path} (images: {img_count})")
    # Save cache info for analytics and UI
    cache_json_path = Path("image_cache.json")
    cache = []
    if cache_json_path.exists():
        with open(cache_json_path, "r", encoding="utf-8") as f:
            try:
                cache = json.load(f)
            except Exception:
                cache = []
    # Add all images in cache dir to cache.json with tags and scores
    for img_file in image_cache_dir.glob("*.jpg"):
        for tag in image_tags:
            score = clip_score(img_file, tag)
            cache.append({
                "url": str(img_file),
                "tags": [tag],
                "clip_score": score,
                "used": False,
                "section": None
            })
    # Add used images
    for section, (img_url, tag) in section_to_img.items():
        cache.append({
            "url": img_url,
            "tags": [tag],
            "clip_score": 1.0,  # Used images are always above threshold
            "used": True,
            "section": section
        })
    # Remove duplicates
    seen = set()
    unique_cache = []
    for entry in cache:
        key = (entry["url"], tuple(entry["tags"]))
        if key not in seen:
            unique_cache.append(entry)
            seen.add(key)
    with open(cache_json_path, "w", encoding="utf-8") as f:
        json.dump(unique_cache, f, ensure_ascii=False, indent=2)

def main():
    import sys
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            md_path = Path(arg)
            if not md_path.exists():
                print(f"[WARN] File not found: {md_path}")
                continue
            category = md_path.parts[-2]
            out_article_dir = OUTPUT_ARTICLE_ROOT / category
            out_image_dir = OUTPUT_IMAGE_ROOT / category
            process_article(md_path, out_article_dir, out_image_dir)
    else:
        print("Usage: python fetch_and_insert_images.py <file1.md> <file2.md> ...")
        print("No files specified. Exiting.")
        sys.exit(1)

if __name__ == "__main__":
    main()
