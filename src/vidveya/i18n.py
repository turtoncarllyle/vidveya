"""Internationalization (i18n) module for VidVeya."""
import locale

TRANSLATIONS = {
    "zh": {
        "app_title": "VidVeya · YouTube 视频下载助手",
        "brand_eyebrow": "VIDEO SAVER",
        "nav_new": "↓  新建下载",
        "nav_history": "▤  下载记录",
        "nav_settings": "⚙  设置",
        "nav_exit": "退出软件",
        "nav_checking": "正在检查组件…",
        "nav_ready": "●  下载组件就绪",
        "nav_not_ready": "●  请检查内置组件",
        "nav_check_failed": "●  组件检查失败",
        "dl_heading": "把喜欢的视频，留在本地。",
        "dl_subtitle": "粘贴 YouTube 或 Shorts 链接，选择清晰度，保留画面与声音。",
        "dl_url_placeholder": "https://www.youtube.com/watch?v=…",
        "dl_paste": "粘贴",
        "dl_analyze": "解析视频",
        "dl_analyzing": "解析中…",
        "dl_waiting_title": "等待添加视频",
        "dl_waiting_meta": "支持普通视频与 Shorts",
        "dl_reading_info": "正在读取视频信息…",
        "dl_querying_meta": "正在查询可用清晰度和音轨",
        "dl_error_title": "暂时无法读取视频",
        "dl_error_meta": "检查链接和网络后重新解析",
        "dl_mode_quick": "快速下载",
        "dl_mode_hd": "高清下载",
        "dl_audio_note": "每个选项均包含音频",
        "dl_th_res": "清晰度",
        "dl_th_format": "文件格式 / 编码",
        "dl_th_fps": "帧率",
        "dl_th_size": "预计大小",
        "dl_hint_idle": "解析后显示源视频实际提供的清晰度。",
        "dl_hint_av1": "大小为估计值，实际下载后可能不同。高分辨率 AV1 / VP9 文件需要播放器支持相应编码。",
        "dl_hint_none": "源视频未提供此档位，请切换下载方式。",
        "dl_progress_starting": "准备下载",
        "dl_progress_starting_val": "准备中",
        "dl_progress_downloading_val": "下载中",
        "dl_progress_merging_val": "合并中",
        "dl_progress_verifying_val": "校验中",
        "dl_progress_completed": "下载完成 · 已验证画面与声音",
        "dl_progress_refreshing": "正在刷新所选格式和音频",
        "dl_progress_merging_meta": "正在无损合并画面与声音",
        "dl_progress_verifying_meta": "正在检查视频轨、音频轨和时长",
        "dl_downloaded": "已下载",
        "dl_total_unknown": "总大小待确定",
        "dl_speed": "速度",
        "dl_eta": "剩余",
        "dl_btn_download": "下载所选视频",
        "dl_btn_cancel": "取消下载",
        "dl_btn_cancelling": "正在取消…",
        "dl_btn_play": "播放视频",
        "dl_btn_open_dir": "打开文件夹",
        "dl_save_to": "保存至",
        "hist_heading": "下载记录",
        "hist_subtitle": "成功下载的文件已验证视频轨和音频轨。",
        "hist_th_video": "视频",
        "hist_th_res": "清晰度",
        "hist_th_state": "状态",
        "hist_th_date": "创建时间",
        "hist_empty": "尚无下载记录。",
        "hist_select_hint": "选择记录查看详情。",
        "hist_btn_reveal": "打开所在文件夹",
        "hist_btn_retry": "重新下载",
        "hist_btn_delete": "删除记录",
        "hist_btn_clear": "清空记录",
        "hist_sort_label": "排序",
        "hist_sort_date_desc": "创建时间 (最新)",
        "hist_sort_date_asc": "创建时间 (最早)",
        "hist_sort_name_asc": "视频名称 (A-Z)",
        "hist_sort_name_desc": "视频名称 (Z-A)",
        "hist_menu_play": "▶  播放视频",
        "hist_menu_reveal": "📂  打开所在文件夹",
        "hist_menu_retry": "↺  重新下载",
        "hist_menu_copy_url": "🔗  复制视频链接",
        "hist_menu_copy_title": "📋  复制视频标题",
        "hist_menu_delete": "🗑  删除此记录",
        "hist_confirm_clear_title": "清空下载记录",
        "hist_confirm_clear_msg": "确定要清空已结束任务的记录吗？\n正在进行的任务和已下载的视频文件会保留。",
        "hist_confirm_delete_title": "删除下载记录",
        "hist_confirm_delete_msg": "确定要从记录中移除此项吗？\n（不会删除已下载的文件）",
        "hist_total_records": "共 {count} 条记录",
        "hist_shown_records": "（显示最近 {shown} 条）",
        "hist_sort_header_tip": "点击列头可按该列升/降序排序",
        "hist_file_missing": "文件已被移动或删除。",
        "hist_in_progress": "任务正在进行",
        "set_heading": "设置",
        "set_subtitle": "下载偏好与组件状态都保存在这台电脑上。",
        "set_sec_appearance": "外观与语言",
        "set_theme_label": "界面主题",
        "set_theme_system": "跟随操作系统",
        "set_theme_light": "浅色模式",
        "set_theme_dark": "深色模式",
        "set_lang_label": "界面语言",
        "set_lang_system": "跟随操作系统",
        "set_lang_zh": "简体中文",
        "set_lang_en": "English",
        "set_sec_storage": "保存位置",
        "set_btn_choose_dir": "选择文件夹",
        "set_sec_proxy": "代理地址（可选）",
        "set_proxy_placeholder": "例如 http://127.0.0.1:7890；留空使用系统网络设置",
        "set_proxy_note": "浏览器中的代理扩展不会自动影响桌面助手。代理配置仅保存在本机。",
        "set_sec_window": "关闭窗口时",
        "set_close_minimize": "最小化到任务栏（继续下载）",
        "set_close_exit": "退出软件",
        "set_close_prompt": "关闭时显示操作提示",
        "set_close_note": "最小化后可从任务栏恢复窗口；左侧“退出软件”可直接退出。",
        "set_btn_save": "保存设置",
        "set_save_success": "已保存。设置立即生效，下载设置用于下次下载。",
        "set_sec_auth": "YouTube 登录态",
        "set_auth_use": "使用已导入的登录态",
        "set_btn_import": "导入 Cookie",
        "set_btn_clear": "清除",
        "set_btn_cookie_help": "如何导入 Cookie？",
        "set_auth_notice_saved": "已加密保存登录态，仅此 Windows 用户可读取。",
        "set_auth_notice_empty": "下载会员或私有视频时，请导入已有观看权限账号的 Netscape Cookie TXT。",
        "set_sec_components": "内置组件",
        "set_btn_recheck": "重新检查",
        "set_comp_th_name": "组件",
        "set_comp_th_status": "状态 / 版本",
        "set_comp_ok": "可用",
        "set_comp_error": "异常",
        "set_comp_note": "安装包已包含全部下载组件。更新应用时完整安装新版即可，下载文件和历史会保留。",
        "cookie_guide_title": "如何导入 YouTube Cookie",
        "cookie_guide_content": (
            "【为什么需要 Cookie？】\n"
            "普通公开视频无需导入 Cookie，粘贴链接可直接下载。\n"
            "只有下载频道会员视频、需要登录的受限内容或私有视频时，才需要导入。\n\n"
            "【操作步骤】\n"
            "1. 打开浏览器登录拥有对应会员/播放权限的 YouTube 账号。\n"
            "2. 安装开源扩展「Get cookies.txt LOCALLY」（Chrome / Edge Web Store）。\n"
            "3. 保持在 YouTube 页面，点击扩展图标，导出 Netscape 格式的 cookies.txt 文件。\n"
            "4. 在 VidVeya 设置中点击「导入 Cookie」选中该文件。\n\n"
            "【安全保证】\n"
            "VidVeya 采用 Windows DPAPI 硬件级加密保存凭据，绝不上报服务器；导入成功后建议直接删除明文 TXT 文件。"
        ),
        "state_starting": "准备下载",
        "state_downloading": "正在下载",
        "state_merging": "正在合并",
        "state_verifying": "正在校验",
        "state_completed": "下载完成",
        "state_failed": "下载失败",
        "state_cancelled": "已取消",
        "state_interrupted": "已中断",
    },
    "en": {
        "app_title": "VidVeya · YouTube Video Downloader",
        "brand_eyebrow": "VIDEO SAVER",
        "nav_new": "↓  New Download",
        "nav_history": "▤  History",
        "nav_settings": "⚙  Settings",
        "nav_exit": "Exit",
        "nav_checking": "Checking components…",
        "nav_ready": "●  Components ready",
        "nav_not_ready": "●  Check components",
        "nav_check_failed": "●  Check failed",
        "dl_heading": "Keep your favorite videos locally.",
        "dl_subtitle": "Paste YouTube or Shorts links, choose resolution, preserve video & audio.",
        "dl_url_placeholder": "https://www.youtube.com/watch?v=…",
        "dl_paste": "Paste",
        "dl_analyze": "Analyze",
        "dl_analyzing": "Analyzing…",
        "dl_waiting_title": "Waiting for video",
        "dl_waiting_meta": "Supports regular videos & Shorts",
        "dl_reading_info": "Reading video details…",
        "dl_querying_meta": "Querying resolutions and audio streams",
        "dl_error_title": "Unable to fetch video",
        "dl_error_meta": "Check link and network, then retry",
        "dl_mode_quick": "Quick",
        "dl_mode_hd": "HD",
        "dl_audio_note": "Every option includes audio",
        "dl_th_res": "Resolution",
        "dl_th_format": "Format / Codec",
        "dl_th_fps": "FPS",
        "dl_th_size": "Est. Size",
        "dl_hint_idle": "Available resolutions will show after analysis.",
        "dl_hint_av1": "Size is estimated. High-res AV1 / VP9 files require supported media players.",
        "dl_hint_none": "Not provided by source in this tier. Try switching mode.",
        "dl_progress_starting": "Preparing download",
        "dl_progress_starting_val": "Preparing",
        "dl_progress_downloading_val": "Downloading",
        "dl_progress_merging_val": "Merging",
        "dl_progress_verifying_val": "Verifying",
        "dl_progress_completed": "Download Complete · Audio & Video Verified",
        "dl_progress_refreshing": "Refreshing format and audio streams",
        "dl_progress_merging_meta": "Losslessly merging video and audio",
        "dl_progress_verifying_meta": "Checking video track, audio track and duration",
        "dl_downloaded": "Downloaded",
        "dl_total_unknown": "Size pending",
        "dl_speed": "Speed",
        "dl_eta": "ETA",
        "dl_btn_download": "Download Selected",
        "dl_btn_cancel": "Cancel",
        "dl_btn_cancelling": "Cancelling…",
        "dl_btn_play": "Play Video",
        "dl_btn_open_dir": "Open Folder",
        "dl_save_to": "Save to",
        "hist_heading": "Download History",
        "hist_subtitle": "Completed files are verified with video and audio tracks.",
        "hist_th_video": "Video",
        "hist_th_res": "Resolution",
        "hist_th_state": "Status",
        "hist_th_date": "Date",
        "hist_empty": "No download history.",
        "hist_select_hint": "Select an item to view details.",
        "hist_btn_reveal": "Open Folder",
        "hist_btn_retry": "Redownload",
        "hist_btn_delete": "Delete Record",
        "hist_btn_clear": "Clear History",
        "hist_sort_label": "Sort",
        "hist_sort_date_desc": "Date (Newest)",
        "hist_sort_date_asc": "Date (Oldest)",
        "hist_sort_name_asc": "Title (A-Z)",
        "hist_sort_name_desc": "Title (Z-A)",
        "hist_menu_play": "▶  Play Video",
        "hist_menu_reveal": "📂  Open Containing Folder",
        "hist_menu_retry": "↺  Redownload",
        "hist_menu_copy_url": "🔗  Copy Video URL",
        "hist_menu_copy_title": "📋  Copy Video Title",
        "hist_menu_delete": "🗑  Delete Record",
        "hist_confirm_clear_title": "Clear History",
        "hist_confirm_clear_msg": "Clear the history of finished tasks?\nActive tasks and downloaded files will be kept.",
        "hist_confirm_delete_title": "Delete Record",
        "hist_confirm_delete_msg": "Are you sure you want to remove this record?\n(Downloaded file will not be deleted)",
        "hist_total_records": "{count} records total",
        "hist_shown_records": " (latest {shown} shown)",
        "hist_sort_header_tip": "Click column headers to sort",
        "hist_file_missing": "File has been moved or deleted.",
        "hist_in_progress": "Task in progress",
        "set_heading": "Settings",
        "set_subtitle": "Preferences and component status are stored on this PC.",
        "set_sec_appearance": "Appearance & Language",
        "set_theme_label": "Theme",
        "set_theme_system": "Follow System",
        "set_theme_light": "Light",
        "set_theme_dark": "Dark",
        "set_lang_label": "Language",
        "set_lang_system": "Follow System",
        "set_lang_zh": "简体中文 (Simplified Chinese)",
        "set_lang_en": "English",
        "set_sec_storage": "Save Location",
        "set_btn_choose_dir": "Browse",
        "set_sec_proxy": "Proxy Address (Optional)",
        "set_proxy_placeholder": "e.g. http://127.0.0.1:7890; leave blank for system default",
        "set_proxy_note": "Browser proxy extensions do not affect the desktop app. Stored locally.",
        "set_sec_window": "On Window Close",
        "set_close_minimize": "Minimize to taskbar (continue download)",
        "set_close_exit": "Exit VidVeya",
        "set_close_prompt": "Show prompt when closing",
        "set_close_note": "Restore from the taskbar; click 'Exit' on the left to quit directly.",
        "set_btn_save": "Save Settings",
        "set_save_success": "Saved. Preferences take effect immediately.",
        "set_sec_auth": "YouTube Session",
        "set_auth_use": "Use imported session",
        "set_btn_import": "Import Cookie",
        "set_btn_clear": "Clear",
        "set_btn_cookie_help": "How to import Cookie?",
        "set_auth_notice_saved": "Session encrypted with DPAPI; accessible only by current Windows user.",
        "set_auth_notice_empty": "For member-only or private videos, import a Netscape Cookie TXT.",
        "set_sec_components": "Built-in Components",
        "set_btn_recheck": "Recheck",
        "set_comp_th_name": "Component",
        "set_comp_th_status": "Status / Version",
        "set_comp_ok": "Ready",
        "set_comp_error": "Error",
        "set_comp_note": "Installer includes all download tools. Updating preserves settings and history.",
        "cookie_guide_title": "How to Import YouTube Cookies",
        "cookie_guide_content": (
            "[Why are cookies needed?]\n"
            "Public videos do NOT require cookies. Simply paste the link to download.\n"
            "Cookies are only needed for channel-member videos, age-restricted videos, or private videos.\n\n"
            "[Instructions]\n"
            "1. Log in to your YouTube account in your browser and make sure you can watch the video.\n"
            "2. Install the open-source extension 'Get cookies.txt LOCALLY' (Chrome / Edge Web Store).\n"
            "3. On youtube.com, click the extension icon and export the Netscape format cookies.txt file.\n"
            "4. In VidVeya Settings, click 'Import Cookie' and select the file.\n\n"
            "[Security Guarantee]\n"
            "VidVeya encrypts cookies locally via Windows DPAPI and never uploads them. You can delete the plain TXT after importing."
        ),
        "state_starting": "Preparing",
        "state_downloading": "Downloading",
        "state_merging": "Merging",
        "state_verifying": "Verifying",
        "state_completed": "Completed",
        "state_failed": "Failed",
        "state_cancelled": "Cancelled",
        "state_interrupted": "Interrupted",
    }
}

_CURRENT_LANG = "zh"


def detect_system_language() -> str:
    """检测操作系统语言，返回 'zh' 或 'en'。"""
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        lang_id = k32.GetUserDefaultUILanguage() & 0xFF
        if lang_id == 0x04:  # Chinese
            return "zh"
    except Exception:
        pass
    try:
        lang = locale.getlocale()[0]
        if lang and lang.lower().startswith("zh"):
            return "zh"
    except Exception:
        pass
    return "en"


def set_language(lang_code: str) -> str:
    """Set active language ('system', 'zh', or 'en'). Returns resolved language ('zh' or 'en')."""
    global _CURRENT_LANG
    if lang_code == "system" or not lang_code:
        resolved = detect_system_language()
    elif lang_code.startswith("zh"):
        resolved = "zh"
    else:
        resolved = "en"
    _CURRENT_LANG = resolved
    return resolved


def get_current_language() -> str:
    return _CURRENT_LANG


def t(key: str, default: str = "") -> str:
    """Translate key for current language with fallback."""
    table = TRANSLATIONS.get(_CURRENT_LANG, TRANSLATIONS["zh"])
    if key in table:
        return table[key]
    if key in TRANSLATIONS["zh"]:
        return TRANSLATIONS["zh"][key]
    return default or key
