# v0.1.7

## 中文

- 优化下拉列表（QComboBox）弹出层显示与阴影效果，去除冗余滚动条，提升选项展开的流畅度与质感。
- 复选框（QCheckBox）增加清晰的白色选中标记图标，显著改善在浅色与深色主题下的选中状态视觉辨识度。
- 优化设置页“外观与偏好”卡片的排版布局，采用统一网格对齐，改善各控件之间的间距与视觉一致性。
- Windows x64 安装包和便携包统一升级为 `0.1.7`。

## English

- Refine QComboBox dropdown popups with native shadow rendering and adaptive scrollbar policy, eliminating redundant scrollbars.
- Add crisp white checkmark icons to checkboxes (QCheckBox) for clearer visual feedback in both light and dark themes.
- Reorganize the "Appearance & Preferences" settings card with a clean grid layout for improved alignment and spacing.
- Ship Windows x64 installer and portable packages as `0.1.7`.

# v0.1.6

## 中文

- 下载页采用胶囊形搜索框（HeroInput）输入链接，质量选项改为芯片式按钮组（QualityChipWidget），操作更直观。
- 下载记录支持实时搜索过滤，输入关键词即可在当前列表中快速定位，去除页面底部冗余按钮。
- 设置页重组为三个聚合卡片（通用、外观与语言、YouTube 登录态），选项变更实时自动保存，无需手动点击"保存"。
- 扩展中英文 i18n 翻译词条，覆盖新增 UI 控件的全部文案；新增界面现代化相关样式令牌（质量芯片、英雄输入框、操作按钮）。
- Windows x64 安装包和便携包统一升级为 `0.1.6`。

## English

- Replace the download page URL field with a capsule HeroInput and quality selection with a QualityChipWidget chip group for a more intuitive interface.
- Add live search filtering on the history page so users can instantly narrow records by keyword; remove redundant bottom buttons.
- Reorganize Settings into three aggregated cards (General, Appearance & Language, YouTube Session) with auto-save so changes apply immediately without a manual save button.
- Expand i18n tokens for both zh and en to cover all new UI controls; add style tokens for quality chips, hero inputs, and action buttons.
- Ship Windows x64 installer and portable packages as `0.1.6`.

# v0.1.5

## 中文

- 下载记录支持点击视频名、清晰度、状态、创建时间的表头排序，再次点击切换升序/降序，并显示方向箭头。清晰度按数值排序，创建时间使用电脑的本地时区。
- 增加记录总数、右键菜单和双击操作，并在列表上方提示如何使用表头排序。
- 支持删除单项和清空已结束任务的记录。界面与数据库共同保护正在下载、合并、校验的任务，保留异常退出后的恢复入口；删除记录不会删除视频文件。
- 修正排序或后台刷新后选择可能指向另一条记录的问题，播放、重试、删除始终使用当前选中的任务。
- 优化下拉列表、右键菜单、状态标识和侧栏退出按钮，修正排序与下拉箭头的显示，支持浅色与深色主题。
- 页面显示完整记录总数；超过 500 条时明确提示仅展示最近 500 条，“清空记录”涵盖全部已结束任务。
- 延续原编码下载、无损音视频合并和 ffprobe 校验，不自动转码。保留 Cookie 鉴权、关闭窗口设置及 Qt 启动修复。
- Windows x64 安装包和便携包统一升级为 `0.1.5`，中英文 README 同步补充记录管理说明。

## English

- Sort download history by clicking Video, Resolution, Status, or Date headers. Click again to reverse direction, shown by an arrow. Sort resolutions numerically and display times in the computer's local time zone.
- Add record counts, context menus, double-click actions, and a hint explaining header sorting.
- Allow deleting individual records and clearing finished tasks. Both the UI and database protect active downloads, merges, and verification tasks so crash recovery stays available. Downloaded files are kept.
- Keep selection on the same task when sorting or when worker updates refresh the list, preventing actions from targeting a different record.
- Refine dropdowns, context menus, status indicators, and the sidebar Exit button in light and dark themes. Fix sort and dropdown arrow rendering.
- Show the full history count and disclose the latest-500 display limit. Clear History covers all finished records.
- Preserve source codecs, lossless audio/video merging, ffprobe validation, cookie authentication, window-close preferences, and the Qt startup fixes. No automatic transcoding is added.
- Ship Windows x64 installer and portable packages as `0.1.5`, with updated history instructions in both READMEs.

# v0.1.4

## 中文

- 更新下载、记录和设置页面的卡片布局，新增浅色、深色及跟随系统的主题设置，侧栏可快速切换主题。
- 增加简体中文、English 和跟随系统的界面语言选项，重新启动后应用；部分下载状态、诊断和对话框仍为中文。
- 下载卡片显示准备、下载、合并、校验、完成五个阶段，侧栏显示当前任务进度，切换页面仍可查看。
- 下载完成后可直接播放视频或打开文件夹，下载记录增加播放入口。
- 修正卡片内主按钮的背景显示和完成操作栏的间距；下载页在小窗口中可滚动，避免按钮文字被挤压。
- 纳入当前设置页的 Cookie 操作说明入口，中英文 README 提供完整导入指南；Cookie 导入和鉴权流程保持原有实现。
- 保留原编码下载、无损音视频合并和 ffprobe 校验，不自动转码；保留关闭窗口最小化/退出设置及 Qt 启动修复。
- Windows x64 安装包和便携包统一为 `0.1.4`，用户无需单独安装运行环境。

AV1/VP9 输出仍需要播放器支持对应编码。语言选项目前覆盖主要界面，尚未完成全部运行提示的翻译。

## English

- Refresh the download, history, and settings pages with card layouts. Add light, dark, and system theme preferences plus a sidebar theme toggle.
- Add Simplified Chinese, English, and system language options, applied on restart. Some download status messages, diagnostics, and dialogs remain in Chinese.
- Show preparation, download, merge, verification, and completion stages, with a sidebar progress indicator visible across pages.
- Add playback and folder shortcuts after downloads complete, and playback from download history.
- Fix primary button backgrounds inside cards and completion action spacing. Allow scrolling on the download page so small windows do not compress button text.
- Include the current settings-page cookie instructions and full import guides in both READMEs. Cookie import and authentication keep their existing implementation.
- Preserve source codecs, lossless audio/video merging, and ffprobe validation without automatic transcoding. Retain minimize/exit preferences and the Qt startup fixes.
- Ship version `0.1.4` as Windows x64 installer and portable packages, with all required runtimes included.

AV1/VP9 output requires a compatible decoder. Language selection covers the main interface; translation of all runtime messages is not yet complete.

# v0.1.3

## 中文

- 高清下载恢复 `0.1.2` 的逻辑，保留源编码并无损合并音视频，取消耗时的自动 H.264 转码。
- 设置中可选择关闭窗口时“最小化到任务栏（继续下载）”或“退出软件”，支持操作提示和记住选择。
- 左侧新增“退出软件”。最小化保持下载运行；退出时确认并保存中断任务，便于重试。
- 放大下载进度条，显示百分比、已下载/总大小、速度及剩余时间，合并和校验分别显示当前阶段。
- 仍在通过 ffprobe 校验视频轨、音频轨、清晰度和时长后才显示成功，保留 Qt 启动和安装升级修复。
- 版本保持 `0.1.3`，安装版和便携版同步更新。设置、历史和下载文件会保留。

AV1/VP9 文件需要支持相应编码的播放器，例如 VLC 或 mpv；本版不通过转码改变源编码。

## English

- Restore the `0.1.2` HD download behavior: preserve source codecs and merge video and audio without automatic H.264 transcoding.
- Add Settings options to minimize to the taskbar or exit when closing, with an optional prompt that can remember the choice.
- Add an explicit Exit action in the sidebar. Minimizing keeps downloads running; exiting confirms and saves interrupted jobs for retry.
- Enlarge the progress bar and show percentage, transferred/total size, speed, and ETA, with separate merging and verification states.
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
