# VidVeya third-party notices

VidVeya distributes third-party software in its Windows packages. The pinned sources and license obligations below are part of the release record.

| Component | Version | Source | License / note |
| --- | --- | --- | --- |
| yt-dlp | 2026.8.19 | https://github.com/yt-dlp/yt-dlp | Unlicense; bundled dependencies and official binary notices apply |
| yt-dlp-ejs | 0.8.0 | https://github.com/yt-dlp/yt-dlp-ejs | Unlicense; bundled JS dependencies retain their notices |
| FFmpeg | N-126549-ga51bb69b09 | https://github.com/BtbN/FFmpeg-Builds | LGPL build; see the packaged FFmpeg notices |
| Deno | 2.9.6 | https://github.com/denoland/deno | MIT and included third-party notices |
| PySide6-Essentials | 6.11.2 | https://github.com/pyside/pyside-setup | LGPL/GPL/commercial licensing options |
| PyInstaller | 6.22.3 | https://github.com/pyinstaller/pyinstaller | GPL with exception |

The build also includes Python packages required by yt-dlp and Qt. The generated `licenses/python-packages.json` file records their package metadata, and text notices found in distributions are copied into the release build. Do not remove those notices from a redistributed package.

VidVeya itself is MIT licensed. See [`LICENSE`](LICENSE).
