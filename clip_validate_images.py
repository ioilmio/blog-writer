import os
import torch
import clip
from PIL import Image
from pathlib import Path

# --- CONFIG ---
# Use the last batch of images from the previous script
TEST_IMAGES = [
    ("muratori", "strategie-vincenti-per-muratori-come-aumentare-clienti-e-guadagni-introduzione.jpg", "muratori al lavoro"),
    ("muratori", "strategie-vincenti-per-muratori-come-aumentare-clienti-e-guadagni-marketing-per-limpresa-edile.jpg", "strategie di marketing"),
    ("falegnami", "strategie-vincenti-per-falegnami-come-aumentare-la-presenza-online-e-trovare-nuovi-clienti-limportanza-della-presenza-online-per-i-falegnami.jpg", "presenza online falegnami"),
    ("falegnami", "strategie-vincenti-per-falegnami-come-aumentare-la-presenza-online-e-trovare-nuovi-clienti-strategie-di-marketing-digitale-per-falegnami.jpg", "marketing digitale falegnami"),
    ("dog-sitter", "diventare-un-dog-sitter-di-successo-strategie-e-consigli-per-professionisti-requisiti-fondamentali-per-un-dog-sitter.jpg", "dog sitter"),
    ("dog-sitter", "diventare-un-dog-sitter-di-successo-strategie-e-consigli-per-professionisti-strategie-per-trovare-clienti.jpg", "trovare clienti dog sitter"),
]
IMG_ROOT = Path(os.path.expanduser("~/quadro/mestieri/public"))

# --- MAIN ---
def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device)
    threshold = 0.30
    for category, filename, query in TEST_IMAGES:
        img_path = IMG_ROOT / category / filename
        if not img_path.exists():
            print(f"[SKIP] {img_path} does not exist.")
            continue
        print(f"[CLIP] Validating: {img_path} <-> '{query}'")
        pil_image = Image.open(img_path)
        tensor = preprocess(pil_image)
        if isinstance(tensor, torch.Tensor):
            tensor = tensor.unsqueeze(0).to(device)
        else:
            print(f"[ERROR] preprocess did not return a tensor for {img_path}")
            continue
        text = clip.tokenize([query]).to(device)
        with torch.no_grad():
            image_features = model.encode_image(tensor)
            text_features = model.encode_text(text)
            image_features /= image_features.norm(dim=-1, keepdim=True)
            text_features /= text_features.norm(dim=-1, keepdim=True)
            similarity = (image_features @ text_features.T).item()
        status = "ACCEPTED" if similarity >= threshold else "REJECTED"
        print(f"[CLIP] Similarity score: {similarity:.4f} [{status}]\n")

if __name__ == "__main__":
    main()
