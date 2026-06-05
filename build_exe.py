import shutil
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent


def main():
    if not shutil.which("pyinstaller"):
        print("PyInstaller is not installed.")
        print("Install it with: python -m pip install pyinstaller")
        return 1

    spec = APP_DIR / "youtube_downloader.spec"
    if spec.exists():
        spec.unlink()

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name",
        "YouTubeDownloader",
        "youtube_downloader.py",
    ]
    print("Building executable...")
    completed = subprocess.run(cmd)
    if completed.returncode != 0:
        print("Build failed.")
        return completed.returncode

    print("Build complete.")
    print("You can find the launcher in the dist folder: dist\\YouTubeDownloader.exe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
