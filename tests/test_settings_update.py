"""设置中心 + 在线更新 的后端单元测试。

覆盖：
- settings.json 读写往返、白名单过滤、损坏文件容错
- updater 版本比较（_parse_version）
- updater Windows zip asset 匹配（_find_windows_zip）
不访问外网；settings 路径用 tmp_path 隔离。
"""
import json
import os

import pytest

from src.webapp.state import AppState
from src.webapp import updater


# ---------------------------------------------------------------------------
# settings 读写
# ---------------------------------------------------------------------------
@pytest.fixture()
def state_tmp(tmp_path, monkeypatch):
    """把 settings.json 指到临时目录，避免污染真实安装目录。"""
    st = AppState()
    monkeypatch.setattr(AppState, "_install_dir", staticmethod(lambda: str(tmp_path)))
    return st


def test_settings_default_when_no_file(state_tmp):
    s = state_tmp.load_settings()
    assert s["width"] == 104
    assert s["metric"] == "ciede2000"
    assert s["theme"] == "system"
    assert s["segMethod"] == "watershed"


def test_settings_roundtrip(state_tmp):
    state_tmp.save_settings({"width": 80, "brand": "hama", "theme": "dark"})
    s = state_tmp.load_settings()
    assert s["width"] == 80
    assert s["brand"] == "hama"
    assert s["theme"] == "dark"
    # 未改字段保持默认
    assert s["metric"] == "ciede2000"


def test_settings_whitelist_filters_unknown_keys(state_tmp):
    state_tmp.save_settings({"width": 60, "evil_key": "x", "__proto__": {}})
    s = state_tmp.load_settings()
    assert s["width"] == 60
    assert "evil_key" not in s
    assert "__proto__" not in s
    # 磁盘上也不该有
    with open(state_tmp._settings_path(), encoding="utf-8") as f:
        on_disk = json.load(f)
    assert "evil_key" not in on_disk


def test_settings_corrupt_file_falls_back(state_tmp):
    with open(state_tmp._settings_path(), "w", encoding="utf-8") as f:
        f.write("{ not valid json !!!")
    s = state_tmp.load_settings()
    assert s["width"] == 104  # 回落默认


def test_settings_partial_file_merges(state_tmp):
    with open(state_tmp._settings_path(), "w", encoding="utf-8") as f:
        json.dump({"width": 200}, f)
    s = state_tmp.load_settings()
    assert s["width"] == 200
    assert s["brand"] == "mard"  # 其余回落默认


# ---------------------------------------------------------------------------
# updater 版本比较
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("tag,expected", [
    ("v2.3.0", (2, 3, 0)),
    ("2.3.0", (2, 3, 0)),
    ("V2.10.1", (2, 10, 1)),
    ("v2.3.0-beta", (2, 3, 0)),
    ("", (0,)),
    (None, (0,)),
])
def test_parse_version(tag, expected):
    assert updater._parse_version(tag) == expected


def test_version_comparison():
    assert updater._parse_version("v2.4.0") > updater._parse_version("2.3.0")
    assert not (updater._parse_version("v2.3.0") > updater._parse_version("2.3.0"))
    assert updater._parse_version("v2.10.0") > updater._parse_version("2.9.9")
    assert updater._parse_version("v2.3.1") > updater._parse_version("2.3.0")


# ---------------------------------------------------------------------------
# updater asset 匹配
# ---------------------------------------------------------------------------
def _asset(name):
    return {"name": name, "browser_download_url": f"https://example.com/{name}"}


def test_find_windows_zip_matches():
    assets = [
        _asset("PerlerBeadsDesigner-windows-v2.4.0.zip"),
        _asset("PerlerBeadsDesigner-macos-v2.4.0.zip"),
        _asset("source.tar.gz"),
    ]
    url = updater._find_windows_zip(assets)
    assert url == "https://example.com/PerlerBeadsDesigner-windows-v2.4.0.zip"


def test_find_windows_zip_case_insensitive():
    assets = [_asset("PerlerBeadsDesigner-Windows-v2.4.0.ZIP")]
    assert updater._find_windows_zip(assets) is not None


def test_find_windows_zip_none_when_absent():
    assets = [_asset("PerlerBeadsDesigner-macos-v2.4.0.zip"), _asset("app.apk")]
    assert updater._find_windows_zip(assets) is None
    assert updater._find_windows_zip([]) is None
    assert updater._find_windows_zip(None) is None
