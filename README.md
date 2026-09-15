# VidVeya

**Windows 本地 YouTube 视频下载助手 · 保留画面与声音**

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

每个清晰度选项都必须有音频：分离的视频流和音频流会自动合并；合并完成后会检查画面、声音、清晰度和时长。音频不可用或验证失败时任务会失败，不会把无声文件标记为成功。源视频本身静音时，文件会保留源视频的静音状态。

## 会员、私有和受限视频

VidVeya 只使用用户已有的合法观看权限，不绕过 YouTube 的访问控制。频道会员或私有视频需要用户在 YouTube 中具备对应权限，并在“设置 → YouTube 登录态”中主动导入该账号导出的 Netscape 格式 Cookie TXT。登录态会用 Windows DPAPI 加密保存于本机，仅当前 Windows 用户可读取；VidVeya 不上传 Cookie。

Cookie 导入步骤：

1. 在已登录且有权限的浏览器配置中，使用可信的 Cookie 导出工具导出 YouTube 站点 Cookie。
2. 确保文件是 Netscape Cookie TXT 格式，而不是 JSON 或请求头文本。
3. 在 VidVeya 设置中点击“导入 Cookie”，勾选“使用已导入的登录态”。
4. 重新解析视频。会员资格、登录状态和地区权限仍由 YouTube 服务器校验。

Cookie 是敏感登录凭据，请只导入自己的账号并在不再需要时点击“清除”。不要把 Cookie 文件、数据库或日志提交到 GitHub。

## 当前边界

- 支持公开点播视频、公开 Shorts，以及用户已有合法观看权限的会员/私有视频。
- 不支持直播录制、播放列表批量下载、绕过 DRM、绕过地区限制或未授权访问。
- 分辨率按画面短边识别，竖屏 1080×1920 会显示为 1080P。
- MP4 优先采用 H.264；源视频仅提供 AV1/VP9 时会显示编码提示。需要兼容旧播放器时，请选择实际提供的 MP4/H.264 档位。

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
