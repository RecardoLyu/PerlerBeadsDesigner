"""
在线更新：检查 GitHub Release 最新版本、后台下载 Windows zip、退出后引导脚本
覆盖安装目录并重启。仅桌面端（onedir）使用；用 requests 访问外网。

流程：
  check_update()      — 读 latest release，比较版本，找 windows zip asset
  start_download()    — 后台线程流式下载 + 解压到 staging，进度供轮询
  get_progress()      — 前端轮询进度/状态
  apply_and_restart() — 生成引导批处理，启动后 os._exit(0)，脚本覆盖目录并重启
"""
import os
import sys
import json
import shutil
import tempfile
import threading
import subprocess
import zipfile

import requests

from src import __version__

GITHUB_REPO = "RecardoLyu/PerlerBeadsDesigner"
_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_TIMEOUT = 20

# 模块级下载状态（单用户桌面应用）
_state = {
    "status": "idle",      # idle | downloading | extracting | ready | error
    "percent": 0,
    "error": "",
    "staging": "",         # 解压出的 PerlerBeadsDesigner/ 所在目录
    "asset_url": "",
    "latest": "",
}
_lock = threading.RLock()


def _parse_version(tag: str):
    """'v2.3.0' / '2.3.0' -> (2,3,0)；解析失败返回 (0,)。"""
    t = (tag or "").strip().lstrip("vV")
    parts = []
    for p in t.split("."):
        num = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(num) if num else 0)
    return tuple(parts) or (0,)


def _find_windows_zip(assets):
    """在 release assets 里找 Windows zip（CI 命名 PerlerBeadsDesigner-windows-vX.Y.Z.zip）。"""
    for a in assets or []:
        name = (a.get("name") or "").lower()
        if "windows" in name and name.endswith(".zip"):
            return a.get("browser_download_url")
    return None


def check_update() -> dict:
    """请求 GitHub 最新 release，与本地版本比较。返回 dict。"""
    r = requests.get(_API, timeout=_TIMEOUT,
                     headers={"Accept": "application/vnd.github+json"})
    r.raise_for_status()
    data = r.json()
    latest_tag = data.get("tag_name", "")
    latest = latest_tag.lstrip("vV")
    asset_url = _find_windows_zip(data.get("assets"))
    has_update = _parse_version(latest_tag) > _parse_version(__version__)
    with _lock:
        _state["asset_url"] = asset_url or ""
        _state["latest"] = latest
    return {
        "current": __version__,
        "latest": latest,
        "has_update": has_update,
        "notes": (data.get("body") or "").strip(),
        "asset_url": asset_url,
        "release_url": data.get("html_url"),
    }


def get_progress() -> dict:
    with _lock:
        return {k: _state[k] for k in ("status", "percent", "error", "latest")}


def start_download():
    """后台线程下载最新 zip 并解压到 staging。需在 check_update 之后调用。"""
    with _lock:
        if _state["status"] in ("downloading", "extracting"):
            raise RuntimeError("正在下载中，请稍候")
        url = _state["asset_url"]
        if not url:
            raise RuntimeError("未找到 Windows 安装包，请重新检查更新")
        _state.update(status="downloading", percent=0, error="", staging="")
    threading.Thread(target=_download_worker, args=(url,), daemon=True).start()


def _download_worker(url: str):
    try:
        workdir = tempfile.mkdtemp(prefix="pbd_update_")
        zip_path = os.path.join(workdir, "update.zip")
        with requests.get(url, stream=True, timeout=_TIMEOUT) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length") or 0)
            got = 0
            with open(zip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if not chunk:
                        continue
                    f.write(chunk)
                    got += len(chunk)
                    if total:
                        with _lock:
                            _state["percent"] = min(99, int(got * 100 / total))
        with _lock:
            _state.update(status="extracting", percent=99)
        # 解压：zip 根通常是 PerlerBeadsDesigner/ 目录（exe + _internal/）
        extract_root = os.path.join(workdir, "extracted")
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(extract_root)
        staging = _locate_app_dir(extract_root)
        if not staging:
            raise RuntimeError("安装包内未找到 PerlerBeadsDesigner 目录")
        with _lock:
            _state.update(status="ready", percent=100, staging=staging)
    except Exception as e:  # noqa: BLE001 - 任何失败都回报给前端
        with _lock:
            _state.update(status="error", error=str(e))


def _locate_app_dir(root: str):
    """在解压目录里找含 PerlerBeadsDesigner.exe 的那一层。"""
    for dirpath, _dirnames, filenames in os.walk(root):
        if "PerlerBeadsDesigner.exe" in filenames:
            return dirpath
    return None


def apply_and_restart():
    """生成引导批处理，退出当前进程后由脚本覆盖安装目录并重启新 exe。"""
    with _lock:
        if _state["status"] != "ready" or not _state["staging"]:
            raise RuntimeError("更新包尚未就绪，请先下载")
        staging = _state["staging"]
    install_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
        else None
    if not install_dir:
        raise RuntimeError("源码运行模式不支持在线替换，请用打包后的 exe 更新")
    exe_path = os.path.join(install_dir, "PerlerBeadsDesigner.exe")
    bat = os.path.join(tempfile.gettempdir(), "pbd_update.bat")
    pid = os.getpid()
    # 等待当前进程退出 → robocopy 镜像覆盖安装目录 → 启动新 exe → 自删
    script = (
        "@echo off\r\n"
        "setlocal\r\n"
        f'set "SRC={staging}"\r\n'
        f'set "DST={install_dir}"\r\n'
        f'set "EXE={exe_path}"\r\n'
        ":wait\r\n"
        f'tasklist /FI "PID eq {pid}" /NH 2>nul | find /i "{pid}" >nul\r\n'
        "if %errorlevel%==0 (timeout /t 1 /nobreak >nul & goto wait)\r\n"
        'robocopy "%SRC%" "%DST%" /MIR /NFL /NDL /NJH /NJS /R:2 /W:1 >nul\r\n'
        'start "" "%EXE%"\r\n'
        'del "%~f0"\r\n'
    )
    with open(bat, "w", encoding="mbcs", errors="replace") as f:
        f.write(script)
    # 分离启动批处理（不阻塞、独立控制台），随后立即退出当前进程
    subprocess.Popen(["cmd", "/c", bat],
                     creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                     close_fds=True)
    os._exit(0)
