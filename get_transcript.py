import whisper
import os


def transcribe_all_audio(audio_folder="audio"):
    """
    Faster transcription using Whisper SMALL model.
    Works well for Hindi, Bengali, Telugu, Kannada.
    """

    if not os.path.exists(audio_folder):
        print(f"❌ Audio folder not found: {audio_folder}")
        return

    print("⚡ Loading Whisper SMALL model (much faster)...")
    model = whisper.load_model("small")  # FAST + Good accuracy

    audio_files = [
        f for f in os.listdir(audio_folder)
        if f.lower().endswith((".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg"))
    ]

    if not audio_files:
        print("⚠ No audio files found.")
        return

    for audio in audio_files:
        audio_path = os.path.join(audio_folder, audio)
        base_name = os.path.splitext(audio)[0]
        output_file = f"{base_name}_transcript.txt"

        print(f"\n🎤 Transcribing {audio} ...")

        try:
            result = model.transcribe(audio_path, fp16=False)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(result["text"])
            print(f"✅ Saved: {output_file}")

        except Exception as e:
            print(f"❌ Error processing {audio}: {e}")

    print("\n🎉 Fast transcription completed!")


# Run
transcribe_all_audio("audio")
