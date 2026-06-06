# YouTube Downloader

A Windows GUI wrapper for `yt-dlp` and `ffmpeg` that downloads single YouTube videos or playlists with a simple point-and-click interface.

## Overview

This project provides a Tkinter-based desktop application for Windows. It can:

- Download a single video or an entire playlist
- Choose output container format: `mp4`, `mkv`, `webm`, or `mp3`
- Select video quality options dynamically from available formats
- Preview metadata before downloading
- Show live download progress and a status log
- Auto-install `yt-dlp.exe` and `ffmpeg.exe` when needed

## Included files

- `youtube_downloader.py` — main GUI application
- `build_exe.py` — helper script to package the app with PyInstaller
- `build_exe.bat` — batch wrapper for `build_exe.py`
- `yt-dlp.exe` — bundled downloader binary
- `ffmpeg.exe` — bundled converter binary

## Prerequisites

- Windows 10 / 11
- Python 3.8 or newer
- Internet access for metadata fetching and downloading videos

> If `yt-dlp.exe` or `ffmpeg.exe` are missing, the application downloads them automatically.

## Requirements

- Python installed and available on the system PATH
- `youtube_downloader.py` must be in the current working folder when running
- `yt-dlp.exe` and `ffmpeg.exe` are recommended to be present in the same folder, but the app can auto-download them if missing
- A valid YouTube video or playlist URL

## Running the application

1. Open PowerShell or Command Prompt.
2. Navigate to the project folder:

```powershell
cd "c:\Users\alier\Documents\Youtube_Video_Downloader"
```

3. Run the app with Python:

```powershell
python youtube_downloader.py
```

4. The Tkinter GUI window should open, and you can paste a YouTube URL to start.

## How to use

1. Paste a valid YouTube video or playlist URL into the URL field.
2. Choose whether you want a single video or playlist download.
3. Click **Preview metadata** to load available formats and inspect playlist items.
4. Select the desired format/quality and output type.
5. Choose an output folder.
6. Click **Start download**.

## Download options

- `Single video` — downloads only the supplied URL.
- `Playlist` — downloads all entries from the URL if it is a playlist.
- `Format / quality` — selected from dynamically generated options based on available formats.
- `Subtitles` — choose whether to download subtitles automatically, in English, or download all available subtitles.
- `Output type`:
  - `mp4`, `mkv`, `webm` — download video and audio, remux or merge as needed
  - `mp3` — extract and convert audio only

## Metadata preview

The preview feature fetches metadata from `yt-dlp` and shows:

- video or playlist title
- uploader
- duration
- view count
- thumbnail URL
- estimated file sizes
- playlist entry list and status

This helps verify the media before starting the download.

## Building a standalone Windows executable

If you want a single-file launcher, install PyInstaller and run the build helper.

1. Install PyInstaller:

```powershell
python -m pip install pyinstaller
```

2. Build the executable:

```powershell
python build_exe.py
```

3. Or run the batch helper:

```powershell
build_exe.bat
```

4. The application binary will be created as:

```powershell
dist\YouTubeDownloader.exe
```

## Troubleshooting

- If the app cannot download media, verify the URL is correct and accessible.
- If preview metadata fails, check your internet connection.
- For audio extraction, select `mp3` and ensure `ffmpeg.exe` is available.
- If `yt-dlp` or `ffmpeg` fail to download automatically, you can place them manually in the same folder as `youtube_downloader.py`.

## Notes

- The app uses `yt-dlp` for all video metadata and download operations.
- `ffmpeg` is required for audio conversion and format merging.
- Existing downloaded output files are shown in the downloaded list panel.
- The app avoids overwriting files and continues partial downloads when possible.

## Run the app step by step

1. Open PowerShell or Command Prompt.
2. Change directory to the project folder:

```powershell
cd "c:\Users\alier\Documents\Youtube_Video_Downloader"
```

3. Start the application:

```powershell
python youtube_downloader.py
```

4. Wait for the Tkinter GUI window to open.
5. Paste a valid YouTube video or playlist URL into the URL field.
6. Click **Preview metadata** to load available formats and playlist details.
7. Choose `Single video` or `Playlist`, then select the desired format/quality.
8. Select an output folder for the downloaded file(s).
9. Click **Start download**.
10. Watch the progress log until the download finishes.
11. Open the chosen output folder to find your downloaded video or audio file.
