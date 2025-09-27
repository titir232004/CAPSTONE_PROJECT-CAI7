import sys
import yaml
import tempfile
import os
import json
import hashlib
from datetime import datetime, timedelta
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from utils import get_recent_videos, download_audio, transcribe_with_whisper

import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from googletrans import Translator
from langdetect import detect

# ---------- Setup ----------
try:
    nltk.data.find("sentiment/vader_lexicon.zip")
except LookupError:
    nltk.download("vader_lexicon")

sia = SentimentIntensityAnalyzer()
translator = Translator()

# Load ministry keywords
with open("keywords.json", "r", encoding="utf-8") as f:
    ministry_keywords = json.load(f)

# ---------- Language arg ----------
if len(sys.argv) > 1:
    target_lang = sys.argv[1]
else:
    target_lang = None


# ---------- Helpers ----------

def get_sentiment_auto(text):
    """Detects language, translates non-English text to English, returns scores + label."""
    try:
        lang = detect(text)
        translated_text = text
        if lang != "en":
            try:
                translated_text = translator.translate(text, src=lang, dest="en").text
            except Exception as te:
                print(f"⚠️ Translation failed ({te}), using original text")

        scores = sia.polarity_scores(translated_text)
        compound = scores["compound"]
        if compound >= 0.05:
            label = "positive"
        elif compound <= -0.05:
            label = "negative"
        else:
            label = "neutral"

        return scores, label, lang, translated_text
    except Exception as e:
        print(f"⚠️ Sentiment analysis failed: {e}")
        return {"neg": 0, "neu": 1, "pos": 0, "compound": 0}, "neutral", "unknown", text


def identify_ministries(text):
    """Match transcript text against ministry keywords and return ministries + scores."""
    text_lower = text.lower()
    ministry_scores = {}
    for ministry, levels in ministry_keywords.items():
        score = 0
        for kw in levels.get("high_priority", []):
            if kw.lower() in text_lower:
                score = max(score, 0.9)
        for kw in levels.get("medium_priority", []):
            if kw.lower() in text_lower:
                score = max(score, 0.6)
        for kw in levels.get("low_priority", []):
            if kw.lower() in text_lower:
                score = max(score, 0.3)
        if score > 0:
            ministry_scores[ministry.capitalize()] = score

    ministries = sorted(ministry_scores, key=lambda k: ministry_scores[k], reverse=True)
    return ministries, ministry_scores


# ---------- Main Processing ----------

def process_channels():
    with open("channels.yml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    for channel in data.get("channels", []):
        name = channel.get("name", "Unknown")
        channel_lang = channel.get("language", None)

        # ✅ Only process channels matching this subprocess’s language
        if target_lang and channel_lang != target_lang:
            continue

        channel_url = channel.get("channel_url", "").rstrip("/") + "/videos"
        print(f"\nProcessing channel: {name}...")

        videos = get_recent_videos(channel_url)
        if not videos:
            print(f"No videos for {name}")
            continue

        # Filter: last 24h & under 5 min
        valid_videos = []
        cutoff_time = datetime.utcnow() - timedelta(hours=25)

        for v in videos:
            if v.get("is_live") or v.get("live_status") in ("is_upcoming", "premiere"):
                continue
            if v.get("duration", 0) == 0 or v["duration"] > 5 * 60:
                continue

            upload_time = None
            if v.get("upload_time"):
                try:
                    upload_time = datetime.fromisoformat(v["upload_time"].replace("Z", "+00:00"))
                except Exception:
                    print(f"⚠️ Failed to parse upload_time for video {v.get('id')}")
            elif v.get("upload_date"):
                try:
                    upload_time = datetime.strptime(v["upload_date"], "%Y%m%d")
                except Exception:
                    print(f"⚠️ Failed to parse upload_date for video {v.get('id')}")

            if upload_time and upload_time > cutoff_time:
                valid_videos.append((upload_time, v))

        if not valid_videos:
            print(f"No valid videos (≤5 min, last 24h) for {name}")
            continue

        # Sort newest first
        valid_videos.sort(key=lambda x: x[0], reverse=True)

        # ✅ Only process the newest video
        upload_time, video = valid_videos[0]
        video_id = video.get("id")
        url = f"https://www.youtube.com/watch?v={video_id}"

        transcript_text = ""
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            transcript_text = " ".join([entry["text"] for entry in transcript])
            print(f"Captions transcript retrieved for {video_id}.")
        except (TranscriptsDisabled, NoTranscriptFound, Exception) as e:
            print(f"No captions found ({e}), using Whisper for {video_id}...")
            with tempfile.TemporaryDirectory() as tmpdir:
                audio_path = download_audio(url, os.path.join(tmpdir, "audio"))
                if audio_path:
                    transcript_text = transcribe_with_whisper(audio_path, lang_code=None, force_large=False)
                    if transcript_text:
                        print(f"Whisper transcript retrieved for {video_id}.")
                    else:
                        print(f"Whisper produced no transcript for {video_id}.")

        if not transcript_text:
            print(f"No transcript available for {video_id}")
            continue

        # Sentiment + Language
        sentiment_scores, sentiment_label, lang, translated_text = get_sentiment_auto(transcript_text)

        # Ministries
        ministries, ministry_scores = identify_ministries(transcript_text)

        # Unique ID
        article_id = hashlib.md5((name + video_id).encode("utf-8")).hexdigest()
        now_iso = datetime.utcnow().isoformat() + "Z"

        # JSON entry (no summary)
        entry = {
            "id": article_id,
            "source_type": "youtube",
            "source_name": name,
            "timestamp": upload_time.isoformat(),
            "language": lang,
            "title": video.get("title", ""),
            "content": transcript_text,
            "url": url,
            "author": None,
            "ministries": ministries,
            "ministry_scores": ministry_scores,
            "sentiment_score": sentiment_scores["compound"],
            "sentiment_label": sentiment_label,
            "keywords": list(set(transcript_text.split()[:10])),
            "metadata": {
                "scrape_time": now_iso,
                "website_section": "YouTube",
                "content_hash": hashlib.md5(transcript_text.encode("utf-8")).hexdigest()
            }
        }

        # Save into JSON (append, max 5 per channel)
        out_file = f"{name}_summaries.json"

        if os.path.exists(out_file):
            with open(out_file, "r", encoding="utf-8") as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    existing_data = {"channel": name, "processed_at": None, "videos": []}
        else:
            existing_data = {"channel": name, "processed_at": None, "videos": []}

        # Append new, avoid duplicates
        existing_ids = {vid["id"] for vid in existing_data.get("videos", [])}
        if entry["id"] not in existing_ids:
            existing_data["videos"].insert(0, entry)

        # Sort newest first
        existing_data["videos"].sort(key=lambda v: v["timestamp"], reverse=True)

        # Keep max 5
        existing_data["videos"] = existing_data["videos"][:5]
        existing_data["processed_at"] = datetime.utcnow().isoformat()

        # Save back
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)

        print(f"✅ Updated {name}: {len(existing_data['videos'])} videos stored in {out_file}")


if __name__ == "__main__":
    process_channels()
