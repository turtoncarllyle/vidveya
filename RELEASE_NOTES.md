# v0.1.3

## 中文

- 高清下载恢复 `0.1.2` 的逻辑，保留源编码并无损合并音视频，取消耗时的自动 H.264 转码。
- 设置中可选择关闭窗口时“最小化到任务栏（继续下载）”或“退出软件”，支持操作提示和记住选择。
- 左侧新增“退出软件”。最小化保持下载运行；退出时确认并保存中断任务，便于重试。
- 仍在通过 ffprobe 校验视频轨、音频轨、清晰度和时长后才显示成功，保留 Qt 启动和安装升级修复。
- 版本保持 `0.1.3`，安装版和便携版同步更新。设置、历史和下载文件会保留。

AV1/VP9 文件需要支持相应编码的播放器，例如 VLC 或 mpv；本版不通过转码改变源编码。

## English

- Restore the `0.1.2` HD download behavior: preserve source codecs and merge video and audio without automatic H.264 transcoding.
- Add Settings options to minimize to the taskbar or exit when closing, with an optional prompt that can remember the choice.
- Add an explicit Exit action in the sidebar. Minimizing keeps downloads running; exiting confirms and saves interrupted jobs for retry.
- Continue requiring ffprobe checks for video, audio, resolution, and duration before reporting success. Retain the Qt startup and installer upgrade fixes.
- Keep version `0.1.3` for both updated packages, preserving settings, history, and downloaded files.

AV1/VP9 files require a player with the matching decoder, such as VLC or mpv. This build preserves the source codecs.

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
