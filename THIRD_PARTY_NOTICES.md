# VidVeya third-party notices

VidVeya distributes third-party software in its Windows and macOS packages. The pinned sources, architecture and license obligations below are part of the v0.2.0 release record. Generated package folders also contain component metadata and any notices found in the upstream archives.

| Component | Version | Windows x64 | macOS Intel / Apple Silicon | License / note |
| --- | --- | --- | --- | --- |
| yt-dlp | 2026.8.19 | bundled | bundled | Unlicense; bundled dependencies and official notices apply |
| yt-dlp-ejs | 0.8.0 | bundled | bundled | Unlicense; bundled JavaScript dependencies retain their notices |
| Deno | 2.9.6 | `deno-x86_64-pc-windows-msvc.zip` | `deno-x86_64-apple-darwin.zip` / `deno-aarch64-apple-darwin.zip` | MIT and included third-party notices |
| FFmpeg / ffprobe | N-127388-g615b07170e (Windows); n5.0.1-patch3 (macOS) | BtbN LGPL build | ColorsWind LGPL builds for x86_64 and arm64 | LGPL; source and build links are recorded in the platform component manifests |
| PySide6-Essentials | 6.11.2 | bundled | bundled | LGPL/GPL/commercial licensing options |
| PyInstaller | 6.22.3 | build dependency | build dependency | GPL with exception |

Platform manifests are stored in [`scripts/`](scripts/):

- [`components-windows-x64.json`](scripts/components-windows-x64.json)
- [`components-macos-x86_64.json`](scripts/components-macos-x86_64.json)
- [`components-macos-arm64.json`](scripts/components-macos-arm64.json)

The build also includes Python packages required by yt-dlp and Qt. The generated `licenses/python-packages.json` file records package metadata, and text notices found in distributions are copied into the release build. Do not remove those notices from a redistributed package.

VidVeya itself is MIT licensed. See [`LICENSE`](LICENSE).
