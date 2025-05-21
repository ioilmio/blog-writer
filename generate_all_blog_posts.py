import json
import os
import requests
from slugify import slugify

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

# Iterate and generate
for category in categories:
    for subs in category.get("subs", []):
        topic = subs["name"]
        additional_context = f"{subs.get('description', '')}\nKeywords: {subs.get('keywords', '')}"
        topic_dir = f"blog-post/{slugify(topic)}"
        for customer_audience in CUSTOMER_AUDIENCE_VALUES:
            for information_type in INFORMATION_TYPE_VALUES:
                if is_done(topic, customer_audience, information_type):
                    print(f"[SKIP] {topic} | {customer_audience} | {information_type}")
                    continue
                print(f"[GENERATE] {topic} | {customer_audience} | {information_type}")
                payload = {
                    "topic": topic,
                    "additional_context": additional_context,
                    "customer_audience": customer_audience,
                    "information_type": information_type,
                    "output_dir": topic_dir,
                    "autosave": True
                }
                try:
                    print(f"[POST] Sending payload: {json.dumps(payload, ensure_ascii=False)}")
                    resp = requests.post(BACKEND_URL, json=payload, timeout=600)
                    resp.raise_for_status()
                    print(f"[RESPONSE] {resp.status_code}: {resp.text}")
                    print(f"[SUCCESS] {topic} | {customer_audience} | {information_type}")
                    mark_done(topic, customer_audience, information_type)
                except Exception as e:
                    print(f"[ERROR] {topic} | {customer_audience} | {information_type} -> {e}")
                    # Do not mark as done, so it can be retried
                    break
