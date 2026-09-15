# VidVeya

**A local Windows YouTube downloader that keeps video and audio together / Windows 本地 YouTube 视频下载助手 · 保留画面与声音**

VidVeya is a standalone Windows desktop app. Paste a YouTube or Shorts URL, choose a source resolution, and download it locally. yt-dlp resolves the streams, FFmpeg merges separate video and audio, and ffprobe verifies the result before VidVeya reports success. No VidVeya server is involved, and users do not need to install Python, Node.js, FFmpeg, or Deno separately.

## Download and install

Get the latest files from [GitHub Releases](https://github.com/turtoncarllyle/vidveya/releases):

- `VidVeya-*-win-x64-setup.exe`: recommended per-user installer; administrator rights are not required.
- `VidVeya-*-win-x64-portable.zip`: extract and run `VidVeya.exe`.

Both packages include Qt, yt-dlp, yt-dlp-ejs, FFmpeg, ffprobe, and Deno. The app checks the bundled components when it starts.

## Usage

1. Open VidVeya.
2. Paste a `watch`, `youtu.be`, or `shorts` URL and choose **Analyze video**.
3. Use **Quick download** for 720p and below, or **HD download** for available 1080p, 2K, 4K, and 8K formats.
4. Choose **Download selected video**.

Every option must have audio. Separate streams are merged automatically, then the result is checked for video, audio, selected resolution, and duration. A missing audio track or failed verification always fails the job; a silent source remains silent.

## Members-only, private, and restricted videos

VidVeya uses only access the user already has and does not bypass YouTube access controls. For a members-only or private video, the logged-in YouTube account must already be authorized. In **Settings → YouTube session**, the user may import a Netscape-format Cookie TXT exported for that account. The session is encrypted with Windows DPAPI and stored locally for the current Windows user; VidVeya never uploads cookies.

Cookies are sensitive credentials. Import only your own account, clear them when no longer needed, and never commit the cookie file, database, or logs to GitHub.

## Boundaries

- Public on-demand videos, public Shorts, and content the user is legally authorized to watch are supported.
- Live recording, playlist batching, DRM bypass, region bypass, and unauthorized access are not supported.
- Resolution is identified by the shorter video dimension, so 1080×1920 is shown as 1080p.
- MP4/H.264 is preferred when YouTube provides it. If only AV1 or VP9 is available, VidVeya shows the codec so the user can choose a compatible player.

## Development

Build with Python 3.12 x64. The provisioning script downloads and verifies pinned Deno, FFmpeg, and Inno Setup releases; runtime components are not committed to the source repository.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.lock
.\.venv\Scripts\python.exe scripts\provision.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src scripts tests
.\.venv\Scripts\python.exe scripts\build.py
```

Build outputs are written to `release/`: installer, portable ZIP, and SHA-256 checksums. Run a public-video smoke test with:

```powershell
.\.venv\Scripts\python.exe scripts\live_check.py --resolution 360
```

## Sources and licenses

- [yt-dlp](https://github.com/yt-dlp/yt-dlp): extraction, format selection, and downloads; Unlicense, with bundled binary dependencies under their own terms.
- [FFmpeg](https://github.com/FFmpeg/FFmpeg): merging and media inspection; the build used here is LGPL.
- [Deno](https://github.com/denoland/deno): yt-dlp YouTube EJS runtime; MIT.
- [PySide6](https://github.com/pyside/pyside-setup): desktop UI; LGPL/GPL/commercial licensing options.
- [PyInstaller](https://github.com/pyinstaller/pyinstaller): packaging; GPL with exception.

See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for pinned versions, sources, and license records. VidVeya source code is MIT licensed; see [`LICENSE`](LICENSE).

## YouTube terms

Download only material you own or are authorized to save, and follow YouTube terms, creator permissions, and applicable law. VidVeya does not bypass paid access, membership, DRM, or other access controls.
