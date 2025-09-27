import yaml
import subprocess
import sys

def main():
    with open("channels.yml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    languages = sorted(set(ch["language"] for ch in data.get("channels", [])))
    print(f"Languages detected: {languages}")

    processes = []
    for lang in languages:
        print(f"Launching transcriber for {lang}...")
        # use sys.executable instead of plain "python"
        p = subprocess.Popen([sys.executable, "transcriber.py", lang])
        processes.append(p)

    for p in processes:
        p.wait()

    print("\n✅ All transcriptions finished.")

if __name__ == "__main__":
    main()
