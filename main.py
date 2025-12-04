import json
import os
import re
import yt_dlp
import whisper
import xml.etree.ElementTree as ET
from datetime import datetime

import requests
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api.formatters import TextFormatter
from googleapiclient.discovery import build
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification


# ========================= CONFIG ============================
API_KEY = "AIzaSyDNaqwdSARzEgeLYpmznozyXAJeS9FhUnI"

channels = {
    "BBC News Hindi": "UCN7B-QD0Qgn2boVH5Q0pOWg",
    "ABP Ananda": "UCv3rFzn-GHGtqzXiaq3sWNg",
    "Kannada One News": "UCH6D0ORSokXupMr7Q-t0NMA",
    "BBC News Telugu": "UCiTCB-B_weEmwHk7ifNobQw"
}

youtube = build('youtube', 'v3', developerKey=API_KEY)

# Whisper
model = whisper.load_model("small")

# Create output folder
os.makedirs("audio", exist_ok=True)
os.makedirs("json_output", exist_ok=True)


# ====================== ZERO-SHOT MINISTRY MODEL ======================
MINISTRIES = [
    "Health ",
    "Education ",
    "Finance ",
    "Agriculture ",
    "Sports",
    "Politics",
    "Defense",
    "International Affairs ",
]

ministry_classifier = pipeline(
    "zero-shot-classification",
    model="facebook/bart-large-mnli"
)


# ====================== SENTIMENT MODEL ======================
def load_sentiment_pipeline():
    try:
        model_name = "md-nishat-008/Mixed-Distil-BERT"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
    except:
        print("⚠ Fallback to multilingual DistilBERT")
        model_name = "distilbert/distilbert-base-multilingual-cased"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)

    return pipeline("sentiment-analysis", model=model, tokenizer=tokenizer)


sentiment_pipeline = load_sentiment_pipeline()


# ========================= FUNCTIONS =============================

def classify_ministry(text):
    text = text.strip()

    if not text or len(text) < 10:
        return "Unrelated / General"

    result = ministry_classifier(text, MINISTRIES)
    return result["labels"][0]


def get_recent_videos(channel_id, max_results=1):
    req = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        order="date",
        maxResults=max_results,
        type="video"
    )
    res = req.execute()
    return res.get("items", [])


# ==================== FIXED download_audio() ====================
def download_audio(video_id, base_path):
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": base_path,
        "quiet": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "m4a",
        }],
        "extractor_args": {
            "youtube": {"player_client": ["android", "web"]}
        }
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

    # Detect actual saved file
    for ext in ["m4a", "webm", "opus", "mp4"]:
        file_path = f"{base_path}.{ext}"
        if os.path.exists(file_path):
            return file_path

    raise FileNotFoundError("yt-dlp did not produce any audio file.")


# ==================== FIXED whisper_transcribe() ====================
def whisper_transcribe(audio_file):
    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"❌ Audio file not found: {audio_file}")

    result = model.transcribe(audio_file)
    return result["text"]


def fetch_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
    except:
        try:
            t_list = YouTubeTranscriptApi.list_transcripts(video_id)
            t_obj = t_list.find_generated_transcript([t.language_code for t in t_list])
            transcript = t_obj.fetch()
        except:
            return None

    formatter = TextFormatter()
    return formatter.format_transcript(transcript)
BACKEND_URL = "https://news-web-scraper-1.onrender.com/api/youtube"
BACKEND_API_KEY = "capstone@2025"
def send_to_backend(payload: dict, timeout: int = 60) -> bool:
    headers = {
        "X-API-KEY": BACKEND_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        print("→ Sending POST request to backend ...")
        r = requests.post(BACKEND_URL, json=payload, headers=headers, timeout=timeout)

        if r.status_code == 200 or r.status_code == 201:
            print(f"✔ Successfully sent to backend ({r.status_code})")
            return True
        else:
            print(f"⚠ Backend returned {r.status_code}: {r.text}")
            return False

    except Exception as e:
        print(f"❌ Failed to send to backend: {e}")
        return False

# ========================= MAIN PROCESS =========================

def process_channel(channel_name, channel_id):
    videos = get_recent_videos(channel_id)

    for video in videos:
        vid = video["id"]["videoId"]
        snippet = video["snippet"]
        title = snippet["title"]
        description = snippet.get("description", "")
        published = snippet.get("publishedAt", "")
        tags = snippet.get("tags", [])

        print(f"\n▶ Processing: {title}")

        transcript_text = fetch_transcript(vid)

        if not transcript_text:
            print("⚠ No transcript, using Whisper...")
            audio_base = f"audio/{channel_name}_{vid}"
            audio_file = download_audio(vid, audio_base)
            transcript_text = whisper_transcribe(audio_file)

        # ---------------- Sentiment ----------------
        sentiment_raw = sentiment_pipeline(transcript_text[:512])[0]
        sentiment_score = float(sentiment_raw["score"])

        def normalize_sentiment(label):
            label = label.lower().strip()

            if label.startswith("label_"):
                num = int(label.split("_")[1])
                if num == 0:
                    return "negative"
                elif num == 1:
                    return "neutral"
                elif num == 2:
                    return "positive"
                return "neutral"

            if "pos" in label:
                return "positive"
            if "neg" in label:
                return "negative"
            if "neu" in label:
                return "neutral"

            return "neutral"

        sentiment_label = normalize_sentiment(sentiment_raw["label"])

        # ---------------- Ministry -----------------
        ministry = classify_ministry(transcript_text[:512])

        # ---------------- Language Detection -----------------
        lang = "Unknown"
        if re.search(r"[\u0900-\u097F]", transcript_text):
            lang = "Hindi"
        elif re.search(r"[\u0C80-\u0CFF]", transcript_text):
            lang = "Kannada"
        elif re.search(r"[\u0980-\u09FF]", transcript_text):
            lang = "Bengali"
        else:
            lang = "English"

        # ---------------- JSON STRUCTURE -----------------
        output = {
            "id": vid,
            "video_id": vid,
            "title": title,
            "description": description,
            "language": lang,
            "channel_name": channel_name,
            "published_at": published,
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "video_url": f"https://www.youtube.com/watch?v={vid}",
            "category": ministry,
            "sentiment_score": sentiment_score,
            "sentiment_label": sentiment_label,
            "metadata": {
                "transcript_length": len(transcript_text),
                "model_used": "Whisper+ZeroShot+Sentiment",
                "source": "youtube + whisper fallback"
            },
        }

        json_path = f"json_output/{channel_name}_{vid}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4, ensure_ascii=False)

        print(f"✔ JSON saved → {json_path}")

        # Backend config

        ok = send_to_backend(output)
        if not ok:
            backup_path = os.path.join("json_output", f"{channel_name}_{vid}.json")
            with open(backup_path, "w", encoding="utf-8") as fh:
                json.dump(output, fh, ensure_ascii=False, indent=2)
            print(f"⚠ Saved backup JSON at {backup_path}")


# ========================= RUN ALL CHANNELS =========================

for name, cid in channels.items():
    process_channel(name, cid)
