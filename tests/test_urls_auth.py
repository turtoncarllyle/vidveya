import sys
from pathlib import Path

import pytest

from vidveya.auth import clear_cookies, cookie_stream, import_cookies, sanitize_cookies, vault_path
from vidveya.engine import friendly_error, ydl_options
from vidveya.models import UserError
from vidveya.urls import normalize_url, validate_proxy


@pytest.mark.parametrize("url", ["https://www.youtube.com/watch?v=YE7VzlLtp-4&list=123", "https://youtu.be/YE7VzlLtp-4?t=1", "https://www.youtube.com/shorts/YE7VzlLtp-4"])
def test_canonical_single_video(url):
    assert normalize_url(url) == "https://www.youtube.com/watch?v=YE7VzlLtp-4"


@pytest.mark.parametrize("url", ["https://youtube.com.evil.test/watch?v=YE7VzlLtp-4", "file:///C:/private.txt", "--exec calc", "https://www.youtube.com/playlist?list=123", "https://www.youtube.com/watch?v=YE7VzlLtp-4&v=aqz-KE-bpKQ", "https://user:pass@www.youtube.com/watch?v=YE7VzlLtp-4", "https://youtu.be:444/YE7VzlLtp-4"])
def test_invalid_urls_rejected(url):
    with pytest.raises(UserError):
        normalize_url(url)


def test_proxy_requires_explicit_valid_address():
    assert validate_proxy("") == ""
    assert validate_proxy("http://127.0.0.1:7890") == "http://127.0.0.1:7890"
    with pytest.raises(UserError):
        validate_proxy("file:///secret")


COOKIE = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t4102444800\tSID\tFAKE_TEST_SESSION_ONLY\n"


def test_cookie_import_filters_unrelated_sites():
    text = COOKIE + ".example.com\tTRUE\t/\tTRUE\t4102444800\tSECRET\tUNRELATED\n"
    assert "UNRELATED" not in sanitize_cookies(text)


@pytest.mark.parametrize("text", ["{\"cookies\": []}", COOKIE.replace("4102444800", "100"), COOKIE.replace("\tTRUE\t/", "\tBAD\t/"), COOKIE.replace(".youtube.com", ".notyoutube.com")])
def test_invalid_cookie_error_never_contains_secret(text):
    with pytest.raises(UserError) as exception:
        sanitize_cookies(text)
    assert "FAKE_TEST_SESSION_ONLY" not in str(exception.value)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI")
def test_dpapi_round_trip_and_memory_only_cookie_jar(tmp_path, monkeypatch):
    # 此测试验证 DPAPI 和 Cookie 传递，组件可用性由媒体测试与打包诊断覆盖。
    monkeypatch.setattr("vidveya.engine.tool", lambda name: tmp_path / f"{name}.exe")
    exported = tmp_path / "cookies.txt"
    exported.write_text(COOKIE, encoding="utf-8")
    assert import_cookies(exported) == 1
    assert b"FAKE_TEST_SESSION_ONLY" not in vault_path().read_bytes()
    assert "FAKE_TEST_SESSION_ONLY" in cookie_stream().read()
    options = ydl_options(use_auth=True)
    assert hasattr(options["cookiefile"], "read")
    assert not isinstance(options["cookiefile"], (str, Path))
    clear_cookies()
    assert not vault_path().exists()


@pytest.mark.parametrize("source,expected", [("Join this channel to get access to members-only content", "会员权限"), ("Private video", "私有"), ("Sign in to confirm your age", "年龄"), ("The uploader has not made this video available in your country", "地区"), ("cookies are no longer valid", "登录态已失效")])
def test_access_errors(source, expected):
    assert expected in friendly_error(Exception(source))
