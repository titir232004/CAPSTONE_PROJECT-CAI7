import os
import tempfile
from yt_dlp import YoutubeDL
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

import whisper

# Add ffmpeg bin folder to PATH
os.environ['PATH'] += os.pathsep + r"E:\ffmpeg-8.0-essentials_build\bin"

MAX_VIDEOS_TO_CHECK = 1
MAX_DURATION_SECONDS = 1200

ydl_opts = {
    'ffmpeg_location': r"E:\ffmpeg-8.0-essentials_build\bin",
    "quiet": False,
    "skip_download": True,
    "extract_flat": True,
    "playlistend": 5,
}


from datetime import datetime, timezone
from yt_dlp import YoutubeDL

MAX_DURATION_SECONDS = 600  # 10 min
MAX_VIDEOS_TO_CHECK = 10    # adjust as needed

ydl_opts = {
    "quiet": True,
    "skip_download": True,
    "extract_flat": False,
    "noplaylist": True,
}


from yt_dlp import YoutubeDL

def get_recent_videos(channel_url, max_results=MAX_VIDEOS_TO_CHECK):
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,   # fast listing
        "playlistend": max_results,
    }

    with YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(channel_url, download=False)
        except Exception as e:
            print(f"❌ Error fetching channel info: {e}")
            return []

        videos = info.get("entries", [])
        resolved = []
        for v in videos:
            try:
                video_url = v.get("url")
                if not video_url and "id" in v:  # fallback
                    video_url = f"https://www.youtube.com/watch?v={v['id']}"

                # 🔎 Now fetch full metadata
                full = ydl.extract_info(video_url, download=False)
                resolved.append(full)
            except Exception as e:
                print(f"⚠️ Skipping {v.get('id')} ({e})")
                continue

        return resolved[:max_results]


def transcribe_with_whisper(audio_path, lang_code, force_large=False):
    model_name = "medium"
    model = whisper.load_model(model_name, device="cpu")

    try:
        result = model.transcribe(audio_path, language=lang_code)
        return result.get("text", "")
    except Exception as e:
        print(f"❌ Whisper error: {e}")
        return ""



def download_audio(video_url, temp_file_without_ext):
    ydl_opts_audio = {
        "quiet": True,
        "format": "bestaudio/best",
        "outtmpl": temp_file_without_ext,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "noplaylist": True,
        "ffmpeg_location": r"E:\ffmpeg-8.0-essentials_build\bin"
    }
    with YoutubeDL(ydl_opts_audio) as ydl:
        ydl.download([video_url])

    final_audio_path = temp_file_without_ext + ".mp3"
    return final_audio_path if os.path.exists(final_audio_path) else None
