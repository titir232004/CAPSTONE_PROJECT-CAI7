import pytesseract
import cv2
import os
import unicodedata
import re
import json
from keywords_and_weights import MINISTRY_KEYWORDS, PRIORITY_WEIGHTS
from transformers import MBartForConditionalGeneration, MBart50TokenizerFast
from rapidfuzz import fuzz

LANG_MAP = {
    "hindi": "hin",
    "bengali": "ben",
    "kannada": "kan"
}
MBART_LANG_CODES = {
    "hindi": "hi_IN",
    "bengali": "bn_IN",
    "kannada": "kn_IN"
}
mbart_model_name = "facebook/mbart-large-50-many-to-many-mmt"
tokenizer = MBart50TokenizerFast.from_pretrained(mbart_model_name)
model = MBartForConditionalGeneration.from_pretrained(mbart_model_name)

def preprocess_image(img_path):
    img = cv2.imread(img_path)
    if img is None:
        raise ValueError(f"Could not load image: {img_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 11)
    return thresh

def ocr_image(img_path, lang_code, debug_out=None):
    processed = preprocess_image(img_path)
    try:
        text = pytesseract.image_to_string(processed, lang=lang_code)
        if debug_out:
            with open(debug_out, "w", encoding="utf-8") as f:
                f.write(text)
        return text
    except Exception as e:
        print(f"OCR extraction failed for {img_path}: {e}")
        return ""

def normalize_text(text):
    text = unicodedata.normalize("NFKC", text.lower())
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def fuzzy_keyword_match_anywhere(keyword, text, min_score=70):
    for win in range(max(3, len(keyword)-2), len(keyword)+3):
        if win > len(text):
            continue
        for i in range(0, len(text) - win + 1):
            chunk = text[i:i+win]
            if fuzz.ratio(chunk, keyword) >= min_score:
                return True
    return False

def classify_article_weighted(text, threshold=3):
    if not text or not text.strip():
        return ["general"], {}, {}
    text_norm = normalize_text(text)
    text_no_space = ''.join(text_norm.split())
    print(f"[DEBUG] Space-free text: {text_no_space[:400]}\n")
    scores = {}
    keyword_hits = {}
    for ministry, levels in MINISTRY_KEYWORDS.items():
        score = 0
        hits = set()
        for prio, kw_set in levels.items():
            for kw in kw_set:
                if len(kw) < 3:
                    continue
                if fuzzy_keyword_match_anywhere(kw, text_no_space, min_score=70):
                    score += PRIORITY_WEIGHTS[prio]
                    hits.add(kw)
        scores[ministry] = score
        keyword_hits[ministry] = list(hits)
    selected = [mn for mn, scr in scores.items() if scr >= threshold]

    if not selected:
        selected = ["general"]
    print(f"[DEBUG] Scores: {scores}")
    print(f"[DEBUG] Keywords hit: {keyword_hits}")
    return selected, scores, keyword_hits

def summarize_text(text, language):
    tgt_lang = MBART_LANG_CODES.get(language, "en_XX")
    tokenizer.src_lang = tgt_lang
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    summary_ids = model.generate(
        inputs["input_ids"],
        num_beams=4,
        max_length=80,
        min_length=15,
        no_repeat_ngram_size=2
    )
    summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
    return summary

def save_output(output, outpath):
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"✅ Output saved at {outpath}")

def main():
    images = [
        ("data/hindi/hindi_sample.jpg", "hindi"),
        ("data/bengali/bengali_sample-1.jpg", "bengali"),
        ("data/kannada/kannada_sample-1.jpg", "kannada")
    ]
    os.makedirs("outputs", exist_ok=True)
    for img_path, lang in images:
        print(f"\n🔎 Processing: {img_path} - [{lang}]")
        lang_code = LANG_MAP[lang]
        txt_file = f"outputs/{lang}_ocr.txt"
        ocr_txt = ocr_image(img_path, lang_code, debug_out=txt_file)
        print(f"[DEBUG] OCR First chars: {ocr_txt[:200]}...\n")
        ministries, scores, hits = classify_article_weighted(ocr_txt, threshold=5)
        summary = summarize_text(ocr_txt, lang) if len(ocr_txt.strip()) > 20 else ""
        output = {
            "language": lang,
            "ministries": ministries,
            "ministry_scores": scores,
            "ministry_hit_keywords": hits,
            "summary": summary,
            "ocr_text": ocr_txt.strip(),
            "source_image": os.path.basename(img_path)
        }
        out_json = f"outputs/{lang}_output.json"
        save_output(output, out_json)

if __name__ == "__main__":
    main()
