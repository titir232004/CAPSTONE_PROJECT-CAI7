import os
import tempfile
import yaml
from yt_dlp import YoutubeDL
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import whisper

MAX_VIDEOS_TO_CHECK = 1  # Only check the first recent suitable video

ydl_opts = {
    "quiet": False,
    "skip_download": True,
    "extract_flat": True,
    "playlistend": 5,  # Limit to first 5 videos only
}

MAX_DURATION_SECONDS = 1200  # 20 minutes


def get_recent_videos(channel_url, max_results=MAX_VIDEOS_TO_CHECK):
    with YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(channel_url, download=False)
            print(f"Info keys: {list(info.keys())}")
        except Exception as e:
            print(f"Error fetching channel info: {e}")
            return []

        videos = info.get("entries", [])
        recent_videos = []
        for video in videos:
            title = video.get("title")
            is_live = video.get("is_live", False)
            duration = video.get("duration", 0)

            print(f"Video: {title} | Duration: {duration} sec | Live: {is_live}")

            if is_live:
                print("Skipping live video")
                continue
            if duration > MAX_DURATION_SECONDS:
                print(f"Skipping due to duration > {MAX_DURATION_SECONDS} sec")
                continue

            recent_videos.append(video)
            if len(recent_videos) >= max_results:
                break
        return recent_videos


def get_transcript(video_id, languages=['hi', 'en']):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
        transcript_text = " ".join([t["text"] for t in transcript_list])
        return transcript_text
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        print(f"No captions available for languages {languages}: {e}")
        return None
    except Exception as e:
        print(f"Error fetching transcript: {e}")
        return None


def download_audio(video_url, temp_file_without_ext):
    ydl_opts_audio = {
        "quiet": False,
        "format": "bestaudio/best",
        "outtmpl": temp_file_without_ext,  # no extension here
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "noplaylist": True,
    }
    with YoutubeDL(ydl_opts_audio) as ydl:
        ydl.download([video_url])

    final_audio_path = temp_file_without_ext + ".mp3"
    if os.path.exists(final_audio_path):
        print(f"Audio downloaded successfully: {final_audio_path}")
        return final_audio_path
    else:
        print(f"Audio file not found after download: {final_audio_path}")
        return None


def transcribe_with_whisper(audio_file, language):
    print(f"Loading larger Whisper model for better Hindi transcription: {language}")
    model = whisper.load_model("medium")  # Use medium model for better accuracy
    result = model.transcribe(audio_file, language=language)
    return result["text"]


def main():
    print("Starting script...\n")
    with open("channels.yml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    aajtak_channel = None
    for ch in data.get("channels", []):
        if ch.get("name", "").strip().lower() == "aaj tak":
            aajtak_channel = ch
            break

    if not aajtak_channel:
        print("Aaj Tak channel info not found in channels.yml")
        return

    # Append /videos to fetch Videos tab only
    channel_url = aajtak_channel.get("channel_url", "").rstrip("/") + "/videos"
    language = aajtak_channel.get("language", "hi")  # Default Hindi
    print(f"Using Videos tab URL: {channel_url}\n")

    videos = get_recent_videos(channel_url, max_results=MAX_VIDEOS_TO_CHECK)
    if not videos:
        print("No videos found matching criteria.")
        return

    recent_video = None
    for vid in videos:
        is_live = vid.get("is_live", False)
        live_status = vid.get("live_status")
        print(f"Considering video: {vid.get('title')} | Live: {is_live} | Status: {live_status}")
        if is_live or (live_status in ["UPCOMING", "LIVE"]):
            print("Skipping live or upcoming video.")
            continue
        recent_video = vid
        break

    if not recent_video:
        print("No suitable recent video found after filtering.")
        return

    title = recent_video.get("title")
    video_id = recent_video.get("id")
    url = f"https://www.youtube.com/watch?v={video_id}"

    print(f"\nSelected video:\nTitle: {title}\nURL: {url}")

    transcript = get_transcript(video_id, languages=[language, 'en'])
    if transcript:
        print("\nTranscript obtained from captions:\n")
        print(transcript[:2000])
    else:
        print("\nNo transcript available from captions. Using Whisper for transcription...")
        with tempfile.TemporaryDirectory() as tmpdir:
            base_audio_path = os.path.join(tmpdir, "audio")  # no extension
            actual_audio_path = download_audio(url, base_audio_path)
            if actual_audio_path:
                transcript_whisper = transcribe_with_whisper(actual_audio_path, language=language)
                print("\nTranscript generated by Whisper:\n")
                print(transcript_whisper[:2000])
            else:
                print("Audio file missing, cannot transcribe.")


if __name__ == "__main__":
    main()
