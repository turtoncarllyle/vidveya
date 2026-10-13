import json
from pathlib import Path
import sys

import vidveya.auth as auth
import vidveya.paths as paths
import vidveya.platforms as platform_adapters
import vidveya.processes as processes


def test_runtime_identifiers_and_macos_directories(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(paths.platform, "machine", lambda: "arm64")
    monkeypatch.setenv("VIDVEYA_DATA_DIR", str(tmp_path / "data"))

    assert paths.runtime_platform() == "macos-arm64"
    assert paths.data_dir() == tmp_path / "data"
    assert paths.downloads_dir() == Path.home() / "Downloads" / "VidVeya"
    assert paths.executable_suffix() == ""


def test_macos_worker_command_uses_extensionless_binary(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(processes.sys, "frozen", True, raising=False)
    monkeypatch.setattr(processes.sys, "executable", str(tmp_path / "VidVeya"), raising=False)
    assert processes.worker_command() == [str(tmp_path / "VidVeya.Worker")]


def test_file_adapters_use_macos_commands(monkeypatch, tmp_path):
    monkeypatch.setattr(platform_adapters.sys, "platform", "darwin")
    calls = []
    monkeypatch.setattr(platform_adapters.subprocess, "Popen", lambda command: calls.append(command))

    platform_adapters.open_file(tmp_path / "视频.mp4")
    platform_adapters.reveal_file(tmp_path / "视频.mp4")
    assert calls == [["open", str(tmp_path / "视频.mp4")], ["open", "-R", str(tmp_path / "视频.mp4")]]


def test_macos_cookie_import_keeps_secret_out_of_marker(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    source = tmp_path / "cookies.txt"
    source.write_text(
        "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t4102444800\tSID\tMAC_SECRET\n",
        encoding="utf-8",
    )
    stored = []
    monkeypatch.setattr(auth, "_keychain_store", lambda payload: stored.append(payload))
    monkeypatch.setenv("VIDVEYA_DATA_DIR", str(tmp_path / "appdata"))

    assert auth.import_cookies(source) == 1
    marker = auth.vault_path()
    assert marker.read_bytes() == b"keychain-v1"
    assert b"MAC_SECRET" in stored[0]
    assert b"MAC_SECRET" not in marker.read_bytes()

    monkeypatch.setattr(auth, "_keychain_load", lambda: stored[0])
    assert "MAC_SECRET" in auth.cookie_stream().read()
    monkeypatch.setattr(auth, "_keychain_clear", lambda: None)
    auth.clear_cookies()
    assert not marker.exists()


def test_platform_component_manifests_are_complete():
    root = Path(__file__).resolve().parents[1] / "scripts"
    for platform_name in ("windows-x64", "macos-x86_64", "macos-arm64"):
        manifest = json.loads((root / f"components-{platform_name}.json").read_text(encoding="utf-8"))
        assert set(manifest) >= {"deno", "ffmpeg"}
        for item in (manifest["deno"], manifest["ffmpeg"]):
            assert item["version"] and item["url"] and len(item["sha256"]) == 64
            assert item.get("license")
