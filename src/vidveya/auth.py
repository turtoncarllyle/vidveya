"""User-selected YouTube cookies, encrypted for the current Windows user."""
import ctypes
from ctypes import wintypes
import io
from pathlib import Path
import sys
import time

from .models import UserError
from .paths import data_dir


def vault_path() -> Path:
    return data_dir() / "youtube-session.bin"


def sanitize_cookies(text: str) -> str:
    if len(text.encode("utf-8")) > 2 * 1024 * 1024:
        raise UserError("Cookie 文件过大，请仅导出 YouTube 站点的 Cookie。")
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() not in {"# Netscape HTTP Cookie File", "# HTTP Cookie File"}:
        raise UserError("请选择 Netscape 格式的 Cookie TXT 文件；不支持 JSON 或复制的请求头。")
    kept = ["# Netscape HTTP Cookie File"]
    for original in lines[1:]:
        if not original.strip() or original.startswith("#") and not original.startswith("#HttpOnly_"):
            continue
        line = original.removeprefix("#HttpOnly_")
        fields = line.split("\t")
        if len(fields) != 7:
            raise UserError("Cookie 文件格式不完整，请重新导出 Netscape 格式的文件。")
        domain, include_subdomains, path, secure, expiry, name, value = fields
        if (include_subdomains not in {"TRUE", "FALSE"} or secure not in {"TRUE", "FALSE"}
                or not path.startswith("/") or not expiry.isdigit() or not name
                or any(ord(character) < 32 for character in "".join(fields))):
            raise UserError("Cookie 文件包含无效记录，请重新导出。")
        domain = domain.lower().lstrip(".")
        if domain != "youtube.com" and not domain.endswith(".youtube.com"):
            continue
        if int(expiry) != 0 and int(expiry) < time.time():
            continue
        kept.append(original)
    if len(kept) == 1:
        raise UserError("文件中没有有效的 YouTube Cookie，登录态可能已过期。请在有权限的账号下重新导出。")
    return "\n".join(kept) + "\n"


def _protect(payload: bytes, decrypt=False) -> bytes:
    if sys.platform != "win32":
        raise UserError("登录态加密功能仅支持 Windows。")

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
    incoming = Blob(len(payload), buffer)
    outgoing = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(incoming), None, None, None, None, 0x1, ctypes.byref(outgoing)):
        raise UserError("无法读取此 Windows 用户的登录态，请清除后重新导入 Cookie。")
    try:
        return ctypes.string_at(outgoing.data, outgoing.size)
    finally:
        ctypes.memset(outgoing.data, 0, outgoing.size)
        kernel.LocalFree(outgoing.data)


def import_cookies(path: Path) -> int:
    if path.stat().st_size > 2 * 1024 * 1024:
        raise UserError("Cookie 文件过大，请仅导出 YouTube 站点 Cookie。")
    try:
        text = sanitize_cookies(path.read_text(encoding="utf-8-sig"))
    except UnicodeError:
        raise UserError("Cookie 文件应为 UTF-8 编码的文本文件。") from None
    target = vault_path()
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(_protect(text.encode("utf-8")))
    temporary.replace(target)
    return len(text.splitlines()) - 1


def cookie_stream() -> io.StringIO:
    try:
        text = _protect(vault_path().read_bytes(), decrypt=True).decode("utf-8")
    except OSError:
        raise UserError("尚未导入登录态。请在设置中导入有观看权限账号的 YouTube Cookie。") from None
    return io.StringIO(sanitize_cookies(text))


def clear_cookies():
    vault_path().unlink(missing_ok=True)
