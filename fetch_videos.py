from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api.formatters import TextFormatter
import yt_dlp
import os
import xml.etree.ElementTree as ET
import whisper

# ================= CONFIG =================
API_KEY = "AIzaSyAoa4aGlW5YosjuNqm6rjKWIHaIpyF6a1o"  # Replace with your API key

channels = {
    "NDTV": "UCZFMm1mMw0F81Z37aaEzTUA",
    "BBC News Hindi": "UCN7B-QD0Qgn2boVH5Q0pOWg",
    "ABP Ananda": "UCv3rFzn-GHGtqzXiaq3sWNg",
    "Kannada One News": "UCH6D0ORSokXupMr7Q-t0NMA",
    "BBC News Telugu": "UCiTCB-B_weEmwHk7ifNobQw"
}

youtube = build('youtube', 'v3', developerKey=API_KEY)
model = whisper.load_model("small")  # Load Whisper once

# Create audio directory if not exists
AUDIO_DIR = "audio"
os.makedirs(AUDIO_DIR, exist_ok=True)


# ================= FUNCTIONS =================

def get_recent_videos(channel_id, max_results=10):
    """
    Fetch recent videos from channel
    """
    request = youtube.search().list(
        part="id",
        channelId=channel_id,
        order="date",
        maxResults=max_results,
        type="video"
    )
    response = request.execute()
    return [item["id"]["videoId"] for item in response.get("items", [])]


def download_audio(video_id, output_file):
    """
    Download best audio from YouTube video using yt-dlp
    """
    ydl_opts = {
        "format": "bestaudio",
        "outtmpl": output_file,
        "quiet": True,
        "noplaylist": True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    return output_file


def fetch_transcript(video_id):
    """
    Fetch transcript (English preferred, fallback to any auto-generated)
    """
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
    except (TranscriptsDisabled, NoTranscriptFound, ET.ParseError, Exception):
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript_obj = transcript_list.find_generated_transcript(
                [t.language_code for t in transcript_list])
            transcript = transcript_obj.fetch()
        except Exception:
            return None

    formatter = TextFormatter()
    return formatter.format_transcript(transcript)


def transcribe_with_whisper(audio_file):
    """
    Transcribe audio using Whisper
    """
    result = model.transcribe(audio_file)
    return result["text"]


# ================= MAIN SCRIPT =================
for channel_name, channel_id in channels.items():
    print(f"[{channel_name}] Searching for a video with transcript...")

    video_ids = get_recent_videos(channel_id)
    transcript_found = False

    for vid in video_ids:
        transcript = fetch_transcript(vid)
        if transcript:
            filename = f"{channel_name}_transcript.txt".replace(" ", "_")
            with open(filename, "w", encoding="utf-8") as f:
                f.write(transcript)
            print(f"[{channel_name}] Transcript saved to {filename}")
            transcript_found = True
            break

    if not transcript_found:
        print(f"[{channel_name}] No transcripts available, using Whisper...")

        if video_ids:
            latest_vid = video_ids[0]

            # Save audio inside audio/ folder
            audio_file = os.path.join(
                AUDIO_DIR,
                f"{channel_name}_audio.m4a".replace(" ", "_")
            )

            download_audio(latest_vid, audio_file)
            print(f"[{channel_name}] Audio downloaded → {audio_file}")

            try:
                whisper_text = transcribe_with_whisper(audio_file)
                filename = f"{channel_name}_whisper_transcript.txt".replace(" ", "_")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(whisper_text)
                print(f"[{channel_name}] Whisper transcript saved to {filename}")
            except Exception as e:
                print(f"[{channel_name}] Whisper transcription failed: {e}")

        else:
            print(f"[{channel_name}] No videos found for this channel.")

