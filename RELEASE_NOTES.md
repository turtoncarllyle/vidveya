# v0.1.3

## 中文

修复高清 MP4 在部分 Windows 播放器中只有声音没有画面的兼容性问题。源视频为 AV1/VP9 时，VidVeya 使用内置 FFmpeg 转换为 H.264，并无损复制音频；H.264 源仍采用无损合并。

## English

Fixes high-definition MP4 files that played audio without video in Windows players lacking AV1/VP9 decoding. When the source uses AV1 or VP9, VidVeya uses the bundled FFmpeg to convert video to H.264 while copying audio without re-encoding; H.264 sources still use lossless remuxing.

# v0.1.2

## 中文

修复安装包升级时残留旧 ICU DLL 的问题。安装新版时会主动删除旧版 icuuc.dll、icudt78.dll 和 icuin.dll，避免它们阻止 PySide6.QtCore 加载。

## English

Fixes in-place upgrades that left stale ICU DLLs from an earlier bundle. The installer now removes old icuuc.dll, icudt78.dll, and icuin.dll files so they cannot prevent PySide6.QtCore from loading.

# v0.1.1

## 中文

修复 Windows 安装版和便携版启动时 PySide6.QtCore 因构建环境 ICU DLL 冲突而无法加载的问题。该版本重新打包 Qt 运行库，并在发布前验证了便携版启动、组件诊断和真实公开视频下载。

## English

Fixes a startup failure in the Windows installer and portable package where PySide6.QtCore could not load because an unrelated ICU DLL from the build environment shadowed the Windows Qt runtime. The Qt runtime was repackaged and the portable build was verified with startup, component diagnostics, and a real public video download.

# v0.1.0

## 中文

VidVeya 首个版本是独立 Windows 视频下载助手：

- 粘贴 YouTube 和 Shorts 链接并解析源视频实际提供的清晰度。
- 快速下载与高清下载视图，支持 144P～8K（以源视频可用格式为准）。
- 独立视频流和音频流自动合并，ffprobe 校验后才显示下载完成。
- 提供进度、速度、剩余时间、取消、重试、下载记录和打开文件夹。
- 默认保存至 `下载\VidVeya`，支持中文文件名、重名保护和自定义保存位置。
- 可导入已有合法观看权限账号的 YouTube Cookie，使用 Windows DPAPI 加密保存会员/私有视频登录态。
- 安装包和便携包内置 Python、Qt、yt-dlp、FFmpeg、ffprobe、Deno，用户无需手动配置运行环境。

### 限制

本版本不支持直播录制、播放列表批量下载、DRM 绕过、地区限制绕过或未授权访问。请只保存你拥有或获授权的内容，并遵循 YouTube 条款及适用法律。

## English

VidVeya 0.1.0 is a standalone Windows video downloader:

- Analyze YouTube and Shorts URLs and show the source formats that are actually available.
- Separate Quick and HD views for 144p–8K, subject to the source formats.
- Merge separate video and audio streams and require ffprobe verification before reporting success.
- Show progress, speed, ETA, cancel/retry actions, history, and reveal-in-folder.
- Save to `Downloads\VidVeya` by default, with Unicode filenames and collision protection.
- Import an existing authorized YouTube session for members-only/private videos; the session is encrypted with Windows DPAPI.
- Installer and portable package include Python, Qt, yt-dlp, FFmpeg, ffprobe, and Deno. No manual runtime setup is required.

### Limitations

Live recording, playlist batching, DRM bypass, region bypass, and unauthorized access are outside this release. Download only content you own or are authorized to save, and follow YouTube terms and applicable law.

### Validation

- Unit and integration tests cover URL validation, format pairing, audio-track requirements, auth storage, media verification, cancellation state, Unicode paths, and 4+ GB file handling.
- A real public YouTube sample was downloaded and verified as H.264 video with AAC stereo audio.
# v0.1.1

## 中文

修复 Windows 安装版和便携版启动时 `PySide6.QtCore` 因构建环境 ICU DLL 冲突而无法加载的问题。该版本重新打包 Qt 运行库，并在发布前验证了便携版启动、组件诊断和真实公开视频下载。

## English

Fixes a startup failure in the Windows installer and portable package where `PySide6.QtCore` could not load because an unrelated ICU DLL from the build environment shadowed the Windows Qt runtime. The Qt runtime was repackaged and the portable build was verified with startup, component diagnostics, and a real public video download.

# v0.1.0
