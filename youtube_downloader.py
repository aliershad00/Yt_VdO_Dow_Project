import json
import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.request
import zipfile
from glob import glob
from pathlib import Path
from tkinter import Tk, StringVar, Text, Scrollbar, filedialog, messagebox, Listbox
from tkinter import BOTH, END, LEFT, RIGHT, Y
from tkinter import ttk

APP_DIR = Path(__file__).resolve().parent
YT_DLP_PATH = APP_DIR / "yt-dlp.exe"
FFMPEG_PATH = APP_DIR / "ffmpeg.exe"
YT_DLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
FFMPEG_ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

PROGRESS_RE = re.compile(r"(?P<pct>\d{1,3}\.\d+)%")
ETA_RE = re.compile(r"ETA\s+(?P<eta>[0-9:]+)")
SPEED_RE = re.compile(r"at\s+(?P<speed>[0-9\.]+\s*[KMG]i?B/s)")

DL_INDEX_RE = re.compile(r"Downloading video (?P<idx>\d+) of (?P<total>\d+)")
DEST_RE = re.compile(r"Destination: (?P<path>.+)")


def download_file(url: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, open(dest, "wb") as out_file:
        shutil.copyfileobj(response, out_file)


def ensure_yt_dlp():
    if YT_DLP_PATH.exists():
        return str(YT_DLP_PATH)
    append_log("Downloading yt-dlp.exe...\n")
    download_file(YT_DLP_URL, YT_DLP_PATH)
    append_log("yt-dlp.exe downloaded.\n")
    return str(YT_DLP_PATH)


def ensure_ffmpeg():
    if FFMPEG_PATH.exists():
        return str(FFMPEG_PATH)
    append_log("Downloading ffmpeg archive...\n")
    temp_zip = APP_DIR / "ffmpeg.zip"
    download_file(FFMPEG_ZIP_URL, temp_zip)
    append_log("Extracting ffmpeg...\n")
    with zipfile.ZipFile(temp_zip, "r") as archive:
        archive.extractall(APP_DIR / "ffmpeg-temp")
    temp_zip.unlink(missing_ok=True)
    candidates = glob(str(APP_DIR / "ffmpeg-temp" / "**" / "ffmpeg.exe"), recursive=True)
    if not candidates:
        raise FileNotFoundError("ffmpeg.exe not found inside downloaded archive")
    shutil.copy2(candidates[0], FFMPEG_PATH)
    shutil.rmtree(APP_DIR / "ffmpeg-temp", ignore_errors=True)
    append_log("ffmpeg.exe installed.\n")
    return str(FFMPEG_PATH)


def append_log(message: str):
    log_text.configure(state="normal")
    log_text.insert(END, message)
    log_text.see(END)
    log_text.configure(state="disabled")


def set_status(message: str):
    status_var.set(message)


def choose_output_folder():
    folder = filedialog.askdirectory(initialdir=output_var.get() or str(APP_DIR))
    if folder:
        output_var.set(folder)


format_map = {}
current_metadata = None


def get_format_option():
    selected = quality_var.get().strip()
    if not selected:
        return "bestvideo+bestaudio/best"

    if selected in format_map:
        return format_map[selected]

    # Accept direct format strings when already provided.
    if selected.startswith("bestvideo+bestaudio/best") or selected.startswith("bestaudio") or selected.startswith("bestvideo["):
        return selected

    # Support direct labels that include a format string after a separator.
    if " - " in selected:
        part = selected.split(" - ", 1)[1].strip()
        if part:
            return part

    return "bestvideo+bestaudio/best"


def human_size(size):
    if not size:
        return "Unknown"
    size = float(size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0 or unit == "TB":
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}PB"


def estimate_combined_size(video_fmt, audio_fmt):
    video_size = video_fmt.get("filesize") or video_fmt.get("filesize_approx") or 0
    audio_size = audio_fmt.get("filesize") or audio_fmt.get("filesize_approx") or 0
    if not video_size and not audio_size:
        return "Unknown"
    return human_size((video_size or 0) + (audio_size or 0))


def estimate_height_quality_size(data, height):
    video = next((fmt for fmt in get_available_formats(data, audio_only=False) if fmt.get("height") and fmt.get("height") <= height), None)
    audio = get_best_audio_format(data)
    if video and audio:
        return estimate_combined_size(video, audio)
    if video:
        return human_size(video.get("filesize") or video.get("filesize_approx"))
    return "Unknown"


def format_label(fmt):
    if not fmt:
        return "Unknown"
    format_id = fmt.get("format_id", "?")
    ext = fmt.get("ext", "")
    vcodec = fmt.get("vcodec", "")
    acodec = fmt.get("acodec", "")
    resolution = fmt.get("resolution") or (f"{fmt.get('height')}p" if fmt.get('height') else "unknown")
    note = fmt.get("format_note") or ""
    size = human_size(fmt.get("filesize") or fmt.get("filesize_approx"))
    kind = "audio" if vcodec == "none" else "video+audio" if acodec != "none" else "video"
    return f"{format_id} - {kind} [{resolution}] {ext} {note} ({size})"


def extract_video_data(data):
    if data.get("_type") == "playlist":
        first = next((entry for entry in data.get("entries", []) if entry), None)
        return first or data
    return data


def find_format_by_id(data, format_id):
    data = extract_video_data(data)
    raw_id = str(format_id)
    base_id = raw_id.split("+")[0] if "+" in raw_id else raw_id
    for fmt in data.get("formats", []):
        if str(fmt.get("format_id")) == base_id:
            return fmt
    return None


def get_best_audio_format(data):
    candidates = get_available_formats(data, audio_only=True)
    return next(iter(candidates), None)


def get_available_formats(data, audio_only=False):
    data = extract_video_data(data)
    formats = data.get("formats", [])
    if audio_only:
        filtered = [fmt for fmt in formats if fmt.get("acodec") != "none" and fmt.get("vcodec") == "none"]
    else:
        filtered = [fmt for fmt in formats if fmt.get("vcodec") != "none"]
    if not filtered:
        filtered = [fmt for fmt in formats if fmt.get("acodec") != "none" or fmt.get("vcodec") != "none"]
    return sorted(filtered, key=lambda f: ((f.get("height") or 0), (f.get("tbr") or 0), (f.get("asr") or 0)), reverse=True)


def get_all_formats(data):
    if data.get("_type") == "playlist":
        all_formats = []
        for entry in data.get("entries", []):
            if not isinstance(entry, dict):
                continue
            all_formats.extend(entry.get("formats", []) or [])
        return all_formats
    return extract_video_data(data).get("formats", [])


def populate_quality_options(data, audio_only=False):
    format_map.clear()
    if audio_only:
        format_map["Audio only - bestaudio"] = "bestaudio"
    else:
        format_map["Max quality - bestvideo+bestaudio/best"] = "bestvideo+bestaudio/best"

    all_formats = get_all_formats(data)
    heights = set()
    for fmt in all_formats:
        if fmt.get("vcodec") == "none":
            continue
        height = fmt.get("height")
        if not height:
            res = fmt.get("resolution")
            if res and isinstance(res, str) and "x" in res:
                try:
                    height = int(res.split("x")[-1])
                except Exception:
                    height = None
        if height:
            heights.add(int(height))

    sorted_heights = sorted(heights, reverse=True)
    for height in sorted_heights:
        label = f"{height}p"
        format_map[label] = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"

    values = list(format_map.keys())
    quality_box.configure(values=values)
    if values:
        quality_var.set(values[0])


video_entries = []  # list of dicts: {'index', 'title', 'duration', 'status', 'id'}


def populate_videos_list(data):
    """Populate the videos tree from metadata (single video or playlist)."""
    global video_entries
    video_entries = []
    # Clear existing rows
    for r in videos_tree.get_children():
        videos_tree.delete(r)

    if data.get("_type") == "playlist":
        entries = data.get("entries", []) or []
        for i, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                title = str(entry)
                duration = ""
                vid = None
            else:
                title = entry.get("title") or entry.get("id") or "Unknown"
                duration = entry.get("duration_string") or entry.get("duration") or ""
                vid = entry.get("id")
            item = {"index": i, "title": title, "duration": duration, "status": "queued", "id": vid}
            video_entries.append(item)
            videos_tree.insert("", "end", values=(i, title, duration, item["status"]))
    else:
        # single video
        video_data = extract_video_data(data)
        title = video_data.get("title", "Unknown")
        duration = video_data.get("duration_string", "")
        item = {"index": 1, "title": title, "duration": duration, "status": "queued", "id": video_data.get("id")}
        video_entries.append(item)
        videos_tree.insert("", "end", values=(1, title, duration, item["status"]))


def update_video_status(idx, status, dest_path=None):
    """Update status for video at 1-based index and refresh treeview and downloaded list if needed."""
    try:
        item = video_entries[idx - 1]
    except Exception:
        return
    item["status"] = status
    # update treeview row
    children = videos_tree.get_children()
    if 0 <= idx - 1 < len(children):
        videos_tree.item(children[idx - 1], values=(item["index"], item["title"], item.get("duration", ""), item["status"]))
    if dest_path and status == "completed":
        # add to downloaded listbox
        downloaded_listbox.insert(END, os.path.basename(dest_path))


def refresh_downloaded_list():
    downloaded_listbox.delete(0, END)
    out = output_var.get() or str(APP_DIR)
    try:
        for pattern in ("*.mp4", "*.mkv", "*.webm", "*.mp3"):
            for p in sorted(Path(out).glob(pattern)):
                downloaded_listbox.insert(END, p.name)
    except Exception:
        pass


def build_command(url: str):
    ytdlp = ensure_yt_dlp()
    ffmpeg = ensure_ffmpeg()
    if download_type_var.get() == "single":
        output_template = os.path.join(output_var.get(), "%(title)s.%(ext)s")
    else:
        output_template = os.path.join(output_var.get(), "%(playlist_index)03d - %(title)s.%(ext)s")

    cmd = [ytdlp, "-f", get_format_option(), "-o", output_template, url, "--console-title", "--newline"]
    if download_type_var.get() == "single":
        cmd.append("--no-playlist")
    elif download_type_var.get() == "playlist":
        cmd.append("--yes-playlist")

    if filetype_var.get() == "mp3":
        cmd += ["--extract-audio", "--audio-format", "mp3"]
    else:
        cmd += ["--merge-output-format", filetype_var.get()]

    if ffmpeg:
        cmd += ["--ffmpeg-location", ffmpeg]

    cmd += ["--ignore-errors", "--no-overwrites", "--continue"]
    if filetype_var.get() == "mp3":
        cmd += ["--audio-quality", "0"]

    return cmd


def format_metadata(data: dict) -> str:
    lines = []
    video_data = extract_video_data(data)
    is_playlist = data.get("_type") == "playlist"

    if is_playlist:
        lines.append(f"Playlist title: {data.get('title', 'Unknown')}")
        lines.append(f"Entries: {data.get('n_entries', len(data.get('entries', [])))}")
        lines.append("---")

    lines.append(f"Title: {video_data.get('title', 'Unknown')}")
    lines.append(f"Uploader: {video_data.get('uploader', 'Unknown')}")
    lines.append(f"Duration: {video_data.get('duration_string', 'Unknown')}")
    lines.append(f"Views: {video_data.get('view_count', 'Unknown')}")
    lines.append(f"Thumbnail: {video_data.get('thumbnail', 'Unknown')}")
    lines.append(f"URL: {video_data.get('webpage_url', video_data.get('url', ''))}")
    lines.append(f"Extractor: {video_data.get('extractor', 'Unknown')}")

    if is_playlist:
        lines.append("Preview is based on the first playlist item.")

    selected_format_id = format_map.get(quality_var.get()) or quality_var.get()
    selected_format = find_format_by_id(data, selected_format_id)
    lines.append("---")
    if selected_format_id == "bestaudio":
        lines.append("Selected quality: Audio only")
        best_audio = get_best_audio_format(data)
        if best_audio:
            lines.append(f"Estimated size: {human_size(best_audio.get('filesize') or best_audio.get('filesize_approx'))}")
    elif selected_format_id == "bestvideo+bestaudio/best":
        lines.append("Selected quality: Max available")
        best_video = next((fmt for fmt in get_available_formats(data, audio_only=False)), None)
        best_audio = get_best_audio_format(data)
        if best_video and best_audio:
            lines.append(f"Estimated total size: {estimate_combined_size(best_video, best_audio)}")
    elif selected_format_id.startswith("bestvideo[height<="):
        height = None
        try:
            height = int(selected_format_id.split("bestvideo[height<=")[1].split("]")[0])
        except Exception:
            height = None
        if height:
            lines.append(f"Selected quality: {quality_var.get()}")
            lines.append(f"Estimated total size: {estimate_height_quality_size(data, height)}")
    elif selected_format:
        lines.append(f"Selected quality: {format_label(selected_format)}")
        lines.append(f"Estimated size: {human_size(selected_format.get('filesize') or selected_format.get('filesize_approx'))}")
    else:
        lines.append(f"Selected quality: {quality_var.get()}")

    best_video = None
    if filetype_var.get() == "mp3":
        best_video = next((fmt for fmt in get_available_formats(data, audio_only=True)), None)
    else:
        best_video = next((fmt for fmt in get_available_formats(data, audio_only=False)), None)
    if best_video:
        lines.append(f"Max available quality: {format_label(best_video)}")

    return "\n".join(lines)


def load_metadata(url: str) -> dict:
    ytdlp = ensure_yt_dlp()
    cmd = [ytdlp]
    if download_type_var.get() == "playlist":
        # Use a flat playlist dump for faster listing of playlist entries
        cmd += ["--flat-playlist"]
    cmd += ["--skip-download", "--dump-single-json", url]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Failed to fetch metadata")
    return json.loads(result.stdout)


def preview_thread():
    url = url_var.get().strip()
    if not url:
        messagebox.showwarning("Missing URL", "Please paste a video or playlist URL first.")
        return

    preview_button.configure(state="disabled")
    append_log("Fetching metadata preview...\n")
    set_status("Fetching metadata preview...")
    try:
        global current_metadata
        data = load_metadata(url)
        current_metadata = data
        audio_only = filetype_var.get() == "mp3"
        populate_quality_options(data, audio_only=audio_only)
        # Populate videos list/tree and refresh downloaded files view
        try:
            populate_videos_list(data)
        except Exception:
            pass
        try:
            refresh_downloaded_list()
        except Exception:
            pass
        append_log("Metadata preview ready.\n")
        set_status("Metadata loaded.")
    except Exception as exc:
        append_log(f"Metadata preview error: {exc}\n")
        messagebox.showerror("Metadata error", str(exc))
        set_status("Preview failed.")
    finally:
        preview_button.configure(state="normal")


def download_thread():
    url = url_var.get().strip()
    if not url:
        messagebox.showwarning("Missing URL", "Please paste a video or playlist URL.")
        start_button.configure(state="normal")
        return
    if not output_var.get():
        messagebox.showwarning("Missing path", "Please choose an output folder.")
        start_button.configure(state="normal")
        return

    try:
        cmd = build_command(url)
    except Exception as exc:
        append_log(f"Error preparing download: {exc}\n")
        set_status("Download setup failed.")
        start_button.configure(state="normal")
        return

    append_log(f"Running: {' '.join(cmd)}\n")
    progress_bar['value'] = 0
    set_status("Downloading...")
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    except FileNotFoundError as exc:
        append_log(f"Failed to run yt-dlp: {exc}\n")
        set_status("yt-dlp not found.")
        start_button.configure(state="normal")
        return

    for line in process.stdout:
        stripped = line.strip()
        if not stripped:
            continue
        append_log(stripped + "\n")
        # Check for per-item download notifications and update status
        m_idx = DL_INDEX_RE.search(stripped)
        if m_idx:
            try:
                idx = int(m_idx.group("idx"))
                root.after(0, update_video_status, idx, "downloading")
            except Exception:
                pass
        m_dest = DEST_RE.search(stripped)
        if m_dest:
            path = m_dest.group("path").strip()
            # Try to map destination to the most recently-downloaded queued item
            try:
                # find first item with status 'downloading' or 'queued'
                for it in video_entries:
                    if it["status"] in ("downloading", "queued"):
                        idx = it["index"]
                        root.after(0, update_video_status, idx, "completed", path)
                        break
            except Exception:
                pass
        progress = PROGRESS_RE.search(stripped)
        eta = ETA_RE.search(stripped)
        speed = SPEED_RE.search(stripped)
        if progress:
            percent = float(progress.group("pct"))
            progress_bar['value'] = percent
            status_parts = [f"{percent:.1f}%"]
            if eta:
                status_parts.append(f"ETA {eta.group('eta')}")
            if speed:
                status_parts.append(speed.group("speed"))
            set_status(" | ".join(status_parts))

    process.wait()
    if process.returncode == 0:
        append_log("Download complete.\n")
        progress_bar['value'] = 0
        set_status("Ready to download.")
    else:
        append_log(f"yt-dlp exited with code {process.returncode}.\n")
        set_status("Download failed.")
    start_button.configure(state="normal")


def on_filetype_changed(*args):
    if current_metadata:
        audio_only = filetype_var.get() == "mp3"
        populate_quality_options(current_metadata, audio_only=audio_only)
        try:
            populate_videos_list(current_metadata)
        except Exception:
            pass


def on_start():
    start_button.configure(state="disabled")
    threading.Thread(target=download_thread, daemon=True).start()


def on_preview():
    threading.Thread(target=preview_thread, daemon=True).start()


root = Tk()
root.title("YouTube Downloader")
root.geometry("760x620")
root.resizable(False, False)

style = ttk.Style(root)
if "vista" in style.theme_names():
    style.theme_use("vista")
style.configure("Header.TLabel", font=("Segoe UI", 10, "bold"))
style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"))

url_var = StringVar()
output_var = StringVar(value=str(APP_DIR))
quality_var = StringVar(value="Max quality - bestvideo+bestaudio/best")
filetype_var = StringVar(value="mp4")
filetype_var.trace_add("write", on_filetype_changed)
download_type_var = StringVar(value="single")
status_var = StringVar(value="Ready to download.")

frame = ttk.Frame(root, padding=14)
frame.pack(fill=BOTH, expand=True)

row = 0
label = ttk.Label(frame, text="Video or Playlist URL:", style="Header.TLabel")
label.grid(row=row, column=0, columnspan=4, sticky="w", pady=(0, 6))

row += 1
url_entry = ttk.Entry(frame, textvariable=url_var, width=96)
url_entry.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 10))
preview_button = ttk.Button(frame, text="Preview metadata", command=on_preview, style="Accent.TButton")
preview_button.grid(row=row, column=3, sticky="ew", padx=(10, 0))

row += 1
radio_single = ttk.Radiobutton(frame, text="Single video", variable=download_type_var, value="single")
radio_playlist = ttk.Radiobutton(frame, text="Playlist", variable=download_type_var, value="playlist")
radio_single.grid(row=row, column=0, sticky="w")
radio_playlist.grid(row=row, column=1, sticky="w")

row += 1
quality_label = ttk.Label(frame, text="Format / quality:")
quality_label.grid(row=row, column=0, sticky="w", pady=(10, 4))
quality_box = ttk.Combobox(frame, textvariable=quality_var, values=["Max quality - bestvideo+bestaudio/best"], state="readonly", width=40)
quality_box.grid(row=row, column=1, sticky="w", pady=(10, 4))

filetype_label = ttk.Label(frame, text="Output type:")
filetype_label.grid(row=row, column=2, sticky="w", pady=(10, 4))
filetype_box = ttk.Combobox(frame, textvariable=filetype_var, values=["mp4", "mkv", "webm", "mp3"], state="readonly", width=18)
filetype_box.grid(row=row, column=3, sticky="w", pady=(10, 4))

row += 1
output_label = ttk.Label(frame, text="Output folder:")
output_label.grid(row=row, column=0, sticky="w", pady=(10, 4))
output_entry = ttk.Entry(frame, textvariable=output_var, width=72)
output_entry.grid(row=row, column=1, columnspan=2, sticky="ew", pady=(10, 4))
output_button = ttk.Button(frame, text="Browse...", command=choose_output_folder)
output_button.grid(row=row, column=3, sticky="ew", pady=(10, 4))

row += 1
start_button = ttk.Button(frame, text="Start download", command=on_start, style="Accent.TButton")
start_button.grid(row=row, column=0, columnspan=4, pady=(16, 10), sticky="ew")

row += 1
progress_bar = ttk.Progressbar(frame, length=720, mode="determinate", maximum=100)
progress_bar.grid(row=row, column=0, columnspan=4, pady=(0, 10), sticky="ew")

row += 1
status_label = ttk.Label(frame, textvariable=status_var, anchor="w")
status_label.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(0, 12))

separator = ttk.Separator(frame, orient="horizontal")
separator.grid(row=row + 1, column=0, columnspan=4, sticky="ew", pady=(0, 14))

row += 2
meta_label = ttk.Label(frame, text="Videos to download:", style="Header.TLabel")
meta_label.grid(row=row, column=0, columnspan=4, sticky="w", pady=(0, 6))

row += 1
metadata_frame = ttk.Frame(frame, relief="groove", padding=6)
metadata_frame.grid(row=row, column=0, columnspan=4, sticky="nsew")

# Treeview showing videos and per-item status
videos_tree = ttk.Treeview(metadata_frame, columns=("idx", "title", "duration", "status"), show="headings", height=9)
videos_tree.heading("idx", text="#")
videos_tree.heading("title", text="Title")
videos_tree.heading("duration", text="Duration")
videos_tree.heading("status", text="Status")
videos_tree.column("idx", width=36, anchor="center")
videos_tree.column("title", width=420)
videos_tree.column("duration", width=80, anchor="center")
videos_tree.column("status", width=100, anchor="center")
videos_tree.pack(side=LEFT, fill=BOTH, expand=True)
metadata_scroll = Scrollbar(metadata_frame, command=videos_tree.yview)
metadata_scroll.pack(side=RIGHT, fill=Y)
videos_tree.configure(yscrollcommand=metadata_scroll.set)

# Downloaded list panel (shows files already downloaded in output folder)
row += 1
downloaded_label = ttk.Label(frame, text="Downloaded videos:", style="Header.TLabel")
downloaded_label.grid(row=row, column=0, columnspan=4, sticky="w", pady=(10, 6))

row += 1
downloaded_frame = ttk.Frame(frame, relief="groove", padding=6)
downloaded_frame.grid(row=row, column=0, columnspan=4, sticky="nsew")
downloaded_listbox = Listbox(downloaded_frame, height=5)
downloaded_listbox.pack(side=LEFT, fill=BOTH, expand=True)
dl_scroll = Scrollbar(downloaded_frame, command=downloaded_listbox.yview)
dl_scroll.pack(side=RIGHT, fill=Y)
downloaded_listbox.configure(yscrollcommand=dl_scroll.set)

row += 1
separator2 = ttk.Separator(frame, orient="horizontal")
separator2.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(14, 14))

row += 1
log_label = ttk.Label(frame, text="Download log:", style="Header.TLabel")
log_label.grid(row=row, column=0, columnspan=4, sticky="w", pady=(0, 6))

row += 1
log_frame = ttk.Frame(frame, relief="groove", padding=6)
log_frame.grid(row=row, column=0, columnspan=4, sticky="nsew")
log_text = Text(log_frame, height=10, wrap="word", state="disabled", background="#111", foreground="#ddd")
log_text.pack(side=LEFT, fill=BOTH, expand=True)
scrollbar = Scrollbar(log_frame, command=log_text.yview)
scrollbar.pack(side=RIGHT, fill=Y)
log_text.configure(yscrollcommand=scrollbar.set)

frame.rowconfigure(row, weight=1)
frame.columnconfigure(2, weight=1)

append_log("Ready. Paste a video or playlist URL and click Preview metadata or Start download.\n")
root.mainloop()
