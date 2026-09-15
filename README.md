# VidVeya

[简体中文](README.md) · [English](README.en.md)

**Windows 本地 YouTube 视频下载助手 · 保留画面与声音 / Local Windows YouTube video downloader · video and audio preserved**

VidVeya 是一个独立的 Windows 桌面应用：粘贴 YouTube 或 Shorts 链接，选择源视频实际提供的清晰度，下载完成后由 FFmpeg 合并并由 ffprobe 验证视频轨和音频轨。下载和合并都在本机完成，没有 VidVeya 服务端，也不要求用户另外安装 Python、Node.js、FFmpeg 或 Deno。

## 下载与安装

从 [GitHub Releases](https://github.com/turtoncarllyle/vidveya/releases) 下载：

- `VidVeya-*-win-x64-setup.exe`：推荐，当前用户安装，不需要管理员权限。
- `VidVeya-*-win-x64-portable.zip`：解压后运行 `VidVeya.exe`。

安装包和便携包都内置 Qt、yt-dlp、yt-dlp-ejs、FFmpeg、ffprobe 和 Deno。首次启动会检查组件状态。

## 使用

1. 打开 VidVeya。
2. 粘贴 `watch`、`youtu.be` 或 `shorts` 链接，点击“解析视频”。
3. 在“快速下载”中选择 720P 及以下，或在“高清下载”中选择 1080P、2K、4K、8K 等实际可用档位。
4. 点击“下载所选视频”。

下载过程中显示进度条、百分比、已下载/总大小、速度和预计剩余时间。总大小未知时显示活动进度条；合并、校验分别显示当前阶段，验证完成后才显示 100%。

每个清晰度选项都必须有音频：分离的视频流和音频流会自动合并；合并完成后会检查画面、声音、清晰度和时长。音频不可用或验证失败时任务会失败，不会把无声文件标记为成功。源视频本身静音时，文件会保留源视频的静音状态。

### 关闭窗口

在“设置 → 关闭窗口时”选择“最小化到任务栏（继续下载）”或“退出软件”，点击“保存设置”立即生效。默认关闭时会提示最小化；可在提示中勾选“记住我的选择，不再提示”，或在设置中关闭提示。最小化不会中断任务，点击任务栏图标即可恢复窗口。左侧“退出软件”始终可以退出；有下载进行时会再次确认，并将中断任务保存在下载记录中供重试。

### 外观、语言与快捷操作

在“设置 → 外观与语言”选择浅色、深色或跟随系统的主题，也可以点击侧栏的主题按钮快速切换。语言可选择简体中文、English 或跟随系统，重新启动后应用；部分下载状态、诊断和对话框仍显示中文。

下载时，侧栏显示当前任务进度，切换到记录或设置页仍可查看。完成后可点击“播放视频”或“打开文件夹”；下载记录也提供播放入口。

### 下载记录（0.1.5）

- 点击“视频、清晰度、状态、创建时间”的列头排序，再次点击切换升序/降序，箭头显示当前方向。清晰度按数值排列，时间显示为电脑本地时区；排序和刷新后仍选中原任务。
- 右键记录可播放、打开文件夹、重新下载、复制链接或标题、删除记录。双击已有文件的记录可播放；文件不存在的已结束任务可重新下载。
- “删除记录”和“清空记录”只移除已结束任务的记录，保留正在下载、合并、校验的任务和磁盘上的视频文件。异常退出的任务仍可在重新启动后重试。
- 页面显示记录总数，列表载入最近 500 条并在其中排序；“清空记录”也会处理更早的已结束任务。

## YouTube Cookie 导入指南

当前版本采用“**浏览器导出 Cookie TXT → 导入 VidVeya → 重新解析下载**”的方式。普通公开视频通常不需要导入 Cookie；下载会员、私有等受限视频时，账号必须原本就有观看权限。

“设置 → YouTube 登录态 → 如何导入 Cookie？”也提供简要操作说明。

### 第一步：在浏览器中登录

以 Chrome 为例，打开 YouTube，登录自己的账号，并确认该账号能正常播放要下载的视频。会员视频还需要对应频道和会员等级的权限。

### 第二步：导出 Cookie TXT

1. 安装开源扩展 [Get cookies.txt LOCALLY（Chrome 扩展商店）](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)。[查看扩展源码](https://github.com/kairi003/Get-cookies.txt-LOCALLY)。
2. 保持在**已登录的 YouTube 页面**，点击浏览器右上角的扩展菜单，打开该扩展。
3. 选择 **Netscape** 格式，导出当前 YouTube 站点的 Cookie，保存为 TXT 文件，例如 `cookies.txt`。

不要选 JSON，不要复制浏览器开发者工具里的请求头，也不需要导出所有网站。VidVeya 接受 UTF-8 编码的 Netscape Cookie TXT，文件大小不超过 2 MB。

### 第三步：导入 VidVeya

1. 打开 **设置 → YouTube 登录态**，点击 **导入 Cookie**。
2. 选择刚才保存的 TXT 文件。
3. 出现“已加密保存 … 条 YouTube Cookie”表示文件导入成功。**使用已导入的登录态**会自动勾选，**不需要再次点击“保存设置”**。

### 第四步：重新解析并下载

返回 **新建下载**，粘贴视频链接，点击 **解析视频**，选择清晰度后下载。导入成功只表示文件已经读取并保存；账号登录是否有效、会员资格及视频权限仍由 YouTube 服务器校验。

### 常见问题

| 情况 | 处理方法 |
| --- | --- |
| 提示格式错误 | 重新选择 Netscape 格式导出；把 JSON 文件改名为 TXT 无效。 |
| 文件中没有有效的 YouTube Cookie | 确认已登录、当前页面是 YouTube，然后重新导出该站点的 Cookie。 |
| 提示登录态过期 | 在浏览器重新登录后，重新导出并导入。 |
| 导入成功，但仍提示需要会员权限 | 检查导出的账号、对应频道和会员等级；YouTube Premium 不等于频道会员。 |
| 不再需要使用登录态 | 在“设置 → YouTube 登录态”点击“清除”，后续任务改为未登录访问。 |

#### Cookie 很快失效怎么办？

YouTube 可能会更新浏览器中的登录 Cookie。如果刚导出的文件很快失效，可按 [yt-dlp 官方导出说明](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies) 使用独立的无痕会话：

1. 在 Chrome 扩展管理中打开该导出扩展的“详细信息”，允许它在无痕模式下运行。
2. 关闭其他无痕窗口，再新建一个无痕窗口，登录有观看权限的 YouTube 账号。
3. 在**同一个标签页**打开 [YouTube robots.txt](https://www.youtube.com/robots.txt)，保持只有这一个无痕标签页，再用扩展导出 YouTube 的 Netscape Cookie TXT。
4. 导出后直接关闭无痕窗口，再将文件导入 VidVeya；不要继续在该无痕会话中浏览 YouTube。此方法可减少浏览器更新 Cookie 导致的失效，但不保证登录态永久有效。

Cookie 相当于登录凭据，请勿发送给他人或上传到 GitHub。VidVeya 使用 Windows DPAPI 在本机加密保存登录态，下载时向 YouTube 提供它以验证权限。导入成功后可以删除导出的明文 TXT 文件。

## 当前边界

- 支持公开点播视频、公开 Shorts，以及用户已有合法观看权限的会员/私有视频。
- 不支持直播录制、播放列表批量下载、绕过 DRM、绕过地区限制或未授权访问。
- 分辨率按画面短边识别，竖屏 1080×1920 会显示为 1080P。
- 高清下载采用 `0.1.2` 的逻辑：保留源视频和音频编码，只进行无损合并，不自动转码。MP4 在同档位优先选择 H.264；源为 AV1/VP9 时仍保留原编码。此类文件需要支持相应编码的播放器（例如 VLC 或 mpv）；MP4 文件后缀本身不保证播放器兼容性。

## 开发

需要 Python 3.12 x64。构建脚本会下载并校验固定版本的 Deno、FFmpeg 和 Inno Setup；运行环境不会被打进源码仓库。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.lock
.\.venv\Scripts\python.exe scripts\provision.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src scripts tests
.\.venv\Scripts\python.exe scripts\build.py
```

构建产物位于 `release/`：安装包、便携 ZIP 和 SHA-256 校验文件。真实公开视频下载回归测试：

```powershell
.\.venv\Scripts\python.exe scripts\live_check.py --resolution 360
```

## 项目来源与许可

- [yt-dlp](https://github.com/yt-dlp/yt-dlp)：视频解析、格式选择和下载，Unlicense（发行二进制的依赖按其许可证提供）。
- [FFmpeg](https://github.com/FFmpeg/FFmpeg)：音视频合并和检查，随构建使用 LGPL 构建。
- [Deno](https://github.com/denoland/deno)：yt-dlp 的 YouTube EJS 运行时，MIT。
- [PySide6](https://github.com/pyside/pyside-setup)：桌面界面，LGPL/GPL/商业许可选项。
- [PyInstaller](https://github.com/pyinstaller/pyinstaller)：应用打包，GPL with exception。

详细组件版本、下载地址和许可证记录见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。VidVeya 自身代码采用 MIT 许可证，见 [`LICENSE`](LICENSE)。

## YouTube 条款

请只下载你拥有或已获授权保存的内容，并遵循 YouTube 服务条款、创作者许可和适用法律。VidVeya 不提供绕过付费、会员、DRM 或其他访问控制的功能。
