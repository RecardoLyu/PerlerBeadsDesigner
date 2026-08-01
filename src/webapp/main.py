"""
Desktop entry point: start the local FastAPI server, then open it in a
pywebview window.

Run directly (``python -m src.webapp.main``) for a desktop window, or import
``create_app``/run uvicorn alone for browser-based development.
"""
import threading
import time
import socket
import os
import sys
import traceback

import uvicorn

from .app import app


def _log_path() -> str:
    """日志文件路径：frozen 下放 exe 同目录，开发下放项目根。"""
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'webapp_error.log')
    return os.path.abspath('webapp_error.log')


def _log_error(msg: str):
    """把启动/运行错误写入日志文件并 print（frozen console=False 下靠日志诊断）。"""
    try:
        with open(_log_path(), 'a', encoding='utf-8') as f:
            f.write(msg.rstrip() + '\n')
    except OSError:
        pass
    print(msg)


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_server(port: int, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def start_server(port: int):
    try:
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        server = uvicorn.Server(config)
        server.run()
    except Exception:
        _log_error("服务器启动失败:\n" + traceback.format_exc())


class _NativeDialogs:
    """JS-facing API injected into the pywebview window for native file dialogs.

    The frontend guards on ``window.pywebview && window.pywebview.api`` so the
    browser fallback still works when these are absent.
    """

    def choose_dir(self):
        """Open a native folder picker; return the chosen path or ''."""
        try:
            import webview
            win = webview.windows[0] if webview.windows else None
            if win is None:
                return ""
            res = win.create_file_dialog(webview.OPEN_FOLDER)
            return res[0] if res else ""
        except Exception:
            _log_error("choose_dir 失败:\n" + traceback.format_exc())
            return ""

    def choose_file(self):
        """Open a native image file picker; return the chosen path or ''."""
        try:
            import webview
            win = webview.windows[0] if webview.windows else None
            if win is None:
                return ""
            res = win.create_file_dialog(
                webview.OPEN_DIALOG,
                file_types=("图像文件 (*.png;*.jpg;*.jpeg;*.bmp;*.webp)", "所有文件 (*.*)"))
            return res[0] if res else ""
        except Exception:
            _log_error("choose_file 失败:\n" + traceback.format_exc())
            return ""


def main():
    port = _free_port()
    t = threading.Thread(target=start_server, args=(port,), daemon=True)
    t.start()
    url = f"http://127.0.0.1:{port}/"

    try:
        import webview
    except ImportError:
        # No pywebview: just keep the server up and print the URL.
        _wait_server(port)
        print(f"Web UI 服务已启动: {url}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return

    ready = _wait_server(port)
    if not ready:
        _log_error(f"服务器在 15s 内未就绪（{url}）。若窗口显示『拒绝连接』，"
                   f"请把此日志 {_log_path()} 反馈给开发者。")
    webview.create_window("拼豆图纸设计器 v2", url, width=1280, height=840,
                          min_size=(960, 640), js_api=_NativeDialogs())
    webview.start()


if __name__ == "__main__":
    main()
