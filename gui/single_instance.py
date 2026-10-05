"""单实例机制：第二个进程启动时把文件参数通过本地套接字转发给主实例。"""
from __future__ import annotations

import json
import socket
import threading

PORT = 52715  # 万能格式转换器专用端口


def _encode_args(args: list[str]) -> bytes:
    return json.dumps(args, ensure_ascii=False).encode("utf-8")


def try_forward_to_running(args: list[str]) -> bool:
    """尝试把参数转发给已运行的实例；成功返回 True。"""
    if not args:
        return False
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.6) as s:
            s.sendall(_encode_args(args))
            return True
    except OSError:
        return False


class SingleInstance:
    """在 127.0.0.1:PORT 监听，收到参数后路由到窗口。"""

    def __init__(self, app, window, collect_paths_fn):
        self._app = app
        self._window = window
        self._collect = collect_paths_fn
        self._server = None

    def listen(self, initial_args: list[str]):
        # 本实例是先行者：检查是否已有实例在监听
        if try_forward_to_running(initial_args):
            self._app.quit()
            return
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._server.bind(("127.0.0.1", PORT))
        except OSError:
            return  # 端口被占（异常情况），不影响主功能
        self._server.listen(4)
        t = threading.Thread(target=self._serve, daemon=True)
        t.start()

    def _serve(self):
        while True:
            try:
                conn, _ = self._server.accept()
            except OSError:
                return
            with conn:
                try:
                    buf = b""
                    while True:
                        chunk = conn.recv(65536)
                        if not chunk:
                            break
                        buf += chunk
                    args = json.loads(buf.decode("utf-8") or "[]")
                except (ValueError, OSError):
                    continue
                if not isinstance(args, list):
                    continue
                # 在主线程中执行 UI 操作
                paths = self._collect([str(a) for a in args])
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._show_paths(paths))

    def _show_paths(self, paths):
        if paths:
            self._window.route_paths(paths)
        self._window.showNormal()
        self._window.raise_()
        self._window.activateWindow()
