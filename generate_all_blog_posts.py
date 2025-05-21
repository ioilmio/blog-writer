import requests
import json
import os
from slugify import slugify
from tqdm import tqdm
import time

# Config
BACKEND_URL = "http://localhost:8000/api/generate"
PROGRESS_FILE = "blog-post/.progress.json"
CATEGORIES_FILE = "landing_categories.json"

CUSTOMER_AUDIENCE_VALUES = [True, False]
INFORMATION_TYPE_VALUES = [
    "guide pratiche",
    "ultime tendenze",
    "normative",
    "consigli per professionisti",
    "consigli per clienti"
]

INFORMATION_TYPE_AUDIENCE_MAP = {
    "guide pratiche": [True, False],
    "ultime tendenze": [True, False],
    "normative": [False],  # Only for professionals
    "consigli per professionisti": [False],  # Only for professionals
    "consigli per clienti": [True],  # Only for customers
}

# Load categories
with open(CATEGORIES_FILE, encoding="utf-8") as f:
    categories = json.load(f)

# Load progress
if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, encoding="utf-8") as f:
        progress = json.load(f)
else:
    progress = {}

# Helper to check if done
def is_done(topic, customer_audience, information_type):
    key = f"{topic}|{customer_audience}|{information_type}"
    return progress.get(key, False)

def mark_done(topic, customer_audience, information_type):
    key = f"{topic}|{customer_audience}|{information_type}"
    progress[key] = True
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

def generate_and_save_article(topic, additional_context, customer_audience, information_type, output_dir, professional_copy):
    payload = {
        "topic": topic,
        "additional_context": additional_context,
        "customer_audience": customer_audience,
        "information_type": information_type,
        "output_dir": output_dir,
        "autosave": True,
        "professional_copy": professional_copy
    }
    response = requests.post("http://localhost:8000/api/generate", json=payload)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

def wait_for_backend(url="http://localhost:8000/api/generate", timeout=60, interval=2):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.options(url)
            if r.status_code < 500:
                print("[CHECK] FastAPI backend is up.")
                return True
        except Exception:
            pass
        print("[CHECK] Waiting for FastAPI backend to be available...")
        time.sleep(interval)
    raise RuntimeError(f"FastAPI backend not available at {url} after {timeout} seconds.")

time.sleep(3)  # Wait for backend services to start if running as a VS Code task
wait_for_backend()

start_time = time.time()
cat_bar = tqdm(categories, desc="Categories", dynamic_ncols=True)
for category in cat_bar:
    # Update elapsed time only once per category
    elapsed = time.time() - start_time
    cat_bar.set_postfix({'Elapsed': f'{elapsed/60:.1f} min'})
    subs_list = category.get("subs", [])
    with tqdm(subs_list, desc=f"Subcategories in {category.get('name', '')}", leave=False, dynamic_ncols=True) as subs_bar:
        for subs in subs_bar:
            topic = subs["name"]
            additional_context = f"{subs.get('description', '')}\nKeywords: {subs.get('keywords', '')}"
            topic_dir = f"blog-post/{slugify(topic)}"
            professional_copy = subs.get("professionalCopy", "")
            # Calculate total_articles based on valid combinations only
            valid_combinations = [(aud, info) for info in INFORMATION_TYPE_VALUES for aud in INFORMATION_TYPE_AUDIENCE_MAP[info]]
            total_articles = len(valid_combinations)
            with tqdm(total=total_articles, desc=f"Articles for {topic}", leave=False, dynamic_ncols=True) as article_bar:
                for information_type in INFORMATION_TYPE_VALUES:
                    allowed_audiences = INFORMATION_TYPE_AUDIENCE_MAP[information_type]
                    for customer_audience in allowed_audiences:
                        status_msg = f"{topic} | {customer_audience} | {information_type}"
                        if is_done(topic, customer_audience, information_type):
                            tqdm.write(f"[SKIP] {status_msg}")
                            article_bar.update(1)
                            continue
                        tqdm.write(f"[GENERATE] {status_msg}")
                        try:
                            article = generate_and_save_article(
                                topic,
                                additional_context,
                                customer_audience,
                                information_type,
                                topic_dir,
                                professional_copy
                            )
                            if article:
                                tqdm.write(f"[SUCCESS] {status_msg}")
                                mark_done(topic, customer_audience, information_type)
                            else:
                                tqdm.write(f"[FAIL] {status_msg} (No article returned)")
                        except Exception as e:
                            tqdm.write(f"[ERROR] {status_msg} -> {e}")
                            import traceback
                            tqdm.write(traceback.format_exc())
                            # Do not mark as done, so it can be retried
                            break
                        article_bar.update(1)

elapsed = time.time() - start_time
print(f"\nAll done! Total elapsed time: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")
