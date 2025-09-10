import os
import tempfile
import yaml
from yt_dlp import YoutubeDL
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import whisper

# Add ffmpeg bin folder to PATH so yt-dlp subprocess can find ffmpeg/ffprobe
os.environ['PATH'] += os.pathsep + r'E:\ffmpeg-8.0-essentials_build\bin'

MAX_VIDEOS_TO_CHECK = 1  # Only first video per channel
MAX_DURATION_SECONDS = 1200  # 20 minutes

# Options for extracting video info (flat extract, no download)
ydl_opts = {
    'ffmpeg_location': r'E:\ffmpeg-8.0-essentials_build\bin',  # Your actual ffmpeg directory
    "quiet": False,
    "skip_download": True,
    "extract_flat": True,
    "playlistend": 5,  # Limit to first 5 videos from Videos tab
}


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
        "ffmpeg_location": r"E:\ffmpeg-8.0-essentials_build\bin"  # Add ffmpeg location here
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
    print(f"Loading Whisper medium model for better transcription: {language}")
    model = whisper.load_model("medium")  # Use medium model for better accuracy
    result = model.transcribe(audio_file, language=language)
    return result["text"]


def process_channel(channel):
    name = channel.get("name", "Unknown")
    language = channel.get("language", "en")
    channel_url = channel.get("channel_url", "").rstrip("/") + "/videos"

    print(f"\nProcessing channel: {name} (language: {language})")
    print(f"Channel videos tab URL: {channel_url}")

    videos = get_recent_videos(channel_url, max_results=MAX_VIDEOS_TO_CHECK)
    if not videos:
        print(f"No videos found matching criteria for channel {name}.")
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
        print(f"No suitable recent video found after filtering for channel {name}.")
        return

    title = recent_video.get("title")
    video_id = recent_video.get("id")
    url = f"https://www.youtube.com/watch?v={video_id}"

    print(f"\nSelected video for {name}:\nTitle: {title}\nURL: {url}")

    transcript = get_transcript(video_id, languages=[language, 'en'])
    if transcript:
        print(f"\nTranscript obtained from captions for {name}:\n")
        print(transcript[:2000])
    else:
        print(f"\nNo transcript available from captions for {name}. Using Whisper for transcription...")
        with tempfile.TemporaryDirectory() as tmpdir:
            base_audio_path = os.path.join(tmpdir, "audio")  # no extension
            actual_audio_path = download_audio(url, base_audio_path)
            if actual_audio_path:
                transcript_whisper = transcribe_with_whisper(actual_audio_path, language=language)
                print(f"\nTranscript generated by Whisper for {name}:\n")
                print(transcript_whisper[:2000])
            else:
                print(f"Audio file missing for {name}, cannot transcribe.")


def main():
    print("Starting multi-channel transcription script...\n")
    with open("channels.yml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    channels = data.get("channels", [])
    if not channels:
        print("No channels found in channels.yml")
        return

    for channel in channels:
        process_channel(channel)


if __name__ == "__main__":
    main()
