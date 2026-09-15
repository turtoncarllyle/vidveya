# VidVeya

[简体中文](README.md) · [English](README.en.md)

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

The download card shows a progress bar, percentage, transferred/total size, speed, and estimated time remaining. When the total size is unknown, the bar shows ongoing activity. Merging and verification show their current stage; 100% is displayed only after verification succeeds.

Every option must have audio. Separate streams are merged automatically, then the result is checked for video, audio, selected resolution, and duration. A missing audio track or failed verification always fails the job; a silent source remains silent.

### Closing the window

In **Settings → When closing the window**, choose **Minimize** or **Exit**, then save. By default, closing shows a prompt with minimize selected. Check **Remember my choice, do not ask again** in that prompt, or disable prompts in Settings. Minimizing keeps downloads running; use the taskbar to restore the window. The sidebar **Exit** action always allows you to quit. Exiting during a download requires confirmation and saves the interrupted job in history for retry.

### Appearance, language, and shortcuts (0.1.4)

Choose light, dark, or system theme in **Settings → Appearance & Language**, or use the sidebar theme toggle. Select Simplified Chinese, English, or system language and restart the app to apply it. Some download status messages, diagnostics, and dialogs remain in Chinese.

The sidebar shows the current download's progress even when viewing history or settings. Completed downloads have **Play Video** and **Open Folder** shortcuts; history also provides playback.

## YouTube cookie import guide

The current workflow is **export a Cookie TXT from your browser → import it into VidVeya → analyze the video again**. Public videos usually do not require cookies. Members-only, private, and other restricted videos require an account that already has permission to watch them.

Version `0.1.4` also includes brief instructions under **Settings → YouTube Session → How to import Cookie?** (设置 → YouTube 登录态 → 如何导入 Cookie？).

### Step 1: Sign in using your browser

Using Chrome as an example, open YouTube, sign in to your own account, and confirm that it can play the video. Members-only content requires access to the relevant channel and membership tier.

### Step 2: Export a Cookie TXT

1. Install the open-source extension [Get cookies.txt LOCALLY from the Chrome Web Store](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc). [View its source code](https://github.com/kairi003/Get-cookies.txt-LOCALLY).
2. Keep the **signed-in YouTube page** active, open Chrome's extensions menu, and select the extension.
3. Choose **Netscape** format and export the current YouTube site's cookies to a TXT file, for example `cookies.txt`.

Do not choose JSON or copy a request header from developer tools. You do not need to export all websites. VidVeya accepts UTF-8 Netscape Cookie TXT files up to 2 MB.

### Step 3: Import into VidVeya

1. Open **设置 → YouTube 登录态** and click **导入 Cookie** (Import cookies).
2. Select the exported TXT file.
3. A message beginning with “已加密保存 … 条 YouTube Cookie” confirms that the file was imported. **使用已导入的登录态** (Use imported session) is enabled automatically. **There is no need to click Save settings again.**

### Step 4: Analyze and download again

Return to **新建下载** (New download), paste the URL, click **解析视频** (Analyze video), and select a resolution to download. A successful import confirms that the file was read and saved; YouTube still verifies the session, membership, and video access permissions.

### Troubleshooting

| Situation | What to do |
| --- | --- |
| Invalid format | Export again in Netscape format. Renaming JSON to TXT does not convert it. |
| No valid YouTube cookies | Confirm that you are signed in and the active page is YouTube, then export that site's cookies again. |
| Expired session | Sign in again in the browser, then export and import a fresh file. |
| Import succeeds but membership is still required | Check the exported account, channel, and membership tier. YouTube Premium is different from channel membership. |
| The session is no longer needed | Click **清除** (Clear) under YouTube session; later jobs use signed-out access. |

#### What if cookies stop working soon after export?

YouTube can rotate account cookies in the browser. If exported cookies quickly stop working, follow the [official yt-dlp export guidance](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies) using a separate incognito session:

1. In Chrome's extension manager, open the export extension's details and allow it to run in incognito mode.
2. Close other incognito windows, open a new one, and sign in to the YouTube account with viewing access.
3. In the **same tab**, open [YouTube robots.txt](https://www.youtube.com/robots.txt). Keep this as the only incognito tab, then export YouTube cookies in Netscape format using the extension.
4. Close the incognito window immediately after exporting, then import the file into VidVeya. Do not continue browsing YouTube in that session. This reduces browser-driven cookie rotation; it does not make the session permanent.

Cookies are login credentials: do not share them or upload them to GitHub. VidVeya encrypts the imported session locally using Windows DPAPI and supplies it to YouTube when authenticating downloads. After a successful import, you can delete the exported plaintext TXT file.

## Boundaries

- Public on-demand videos, public Shorts, and content the user is legally authorized to watch are supported.
- Live recording, playlist batching, DRM bypass, region bypass, and unauthorized access are not supported.
- Resolution is identified by the shorter video dimension, so 1080×1920 is shown as 1080p.
- HD downloads use the `0.1.2` behavior: preserve source video and audio codecs and merge without re-encoding. H.264 is preferred for MP4 at the same resolution when available; AV1/VP9 sources keep their original codecs. Use a player with the corresponding decoder, such as VLC or mpv. An MP4 extension alone does not guarantee player compatibility.

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
