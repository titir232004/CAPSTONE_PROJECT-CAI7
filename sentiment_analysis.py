import json
import re
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    pipeline,
)
from youtube_transcript_api import YouTubeTranscriptApi


# --------------------------------------------------------
# 1️⃣ Zero-Shot Ministry Classifier (NO keywords file needed)
# --------------------------------------------------------
def load_ministry_classifier():
    return pipeline(
        "zero-shot-classification",
        model="facebook/bart-large-mnli"
    )

# List of ministries to classify
MINISTRIES = [
    "Health Ministry",
    "Education Ministry",
    "Finance Ministry",
    "Agriculture Ministry",
    "IT Ministry",
    "Home Ministry",
    "Environment Ministry",
    "Transport Ministry",
    "External Affairs Ministry",
    "Unrelated / General"
]


def classify_ministry(text, classifier):
    result = classifier(text, MINISTRIES)
    return result["labels"][0]  # Best match


# --------------------------------------------------------
# 2️⃣ Sentiment Model
# --------------------------------------------------------
def load_sentiment_pipeline():
    try:
        model_name = "md-nishat-008/Mixed-Distil-BERT"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
    except Exception:
        print("⚠ Fallback to multilingual DistilBERT")
        model_name = "distilbert/distilbert-base-multilingual-cased"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)

    return pipeline("sentiment-analysis", model=model, tokenizer=tokenizer)


# --------------------------------------------------------
# 3️⃣ Extract YouTube transcript
# --------------------------------------------------------
def get_transcript(video_url):
    video_id = re.findall(r"v=([a-zA-Z0-9_-]{11})", video_url)
    if not video_id:
        raise ValueError("Invalid YouTube URL")
    video_id = video_id[0]

    transcript = YouTubeTranscriptApi.get_transcript(
        video_id,
        languages=["en", "hi", "bn"]
    )
    return transcript


# --------------------------------------------------------
# 4️⃣ Full Analysis + Save JSON
# --------------------------------------------------------
def analyze_youtube(video_url, output_file="output.json"):
    transcript_list = get_transcript(video_url)

    sentiment_pipeline = load_sentiment_pipeline()
    ministry_classifier = load_ministry_classifier()

    results = []

    for entry in transcript_list:
        text = entry["text"].strip()
        if not text:
            continue

        # Sentiment
        sentiment = sentiment_pipeline(text)[0]

        # Ministry Classification (ZERO-SHOT)
        ministry = classify_ministry(text, ministry_classifier)

        results.append({
            "time": entry["start"],
            "text": text,
            "sentiment": sentiment["label"],
            "sentiment_score": float(sentiment["score"]),
            "ministry": ministry
        })

    # Save output JSON
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)

    print(f"✅ Analysis done. JSON saved to {output_file}")
    return results


# --------------------------------------------------------
# 5️⃣ Run
# --------------------------------------------------------
if __name__ == "__main__":
    url = "YOUR_YOUTUBE_URL_HERE"
    analyze_youtube(url)
