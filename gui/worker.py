"""后台转换线程：并行执行、可取消，通过信号汇报每一行的进度。"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from core import registry
from core.utils import ConvertCancelled, ConvertError


class ConvertWorker(QThread):
    row_started = Signal(int)
    row_done = Signal(int, str, str, list)  # 行号, 状态(ok/fail/skip), 消息, 输出文件列表
    progress = Signal(int, int)             # 已完成数, 总数
    all_done = Signal(int, int, str)        # 成功数, 失败/跳过数, 汇总消息

    def __init__(self, rows: list[tuple[int, Path]], target: str,
                 out_dir: Path | None, options: dict, merge_pdf: bool = False,
                 merge_kind: str = "images", parent=None):
        super().__init__(parent)
        self._rows = rows
        self._target = target
        self._out_dir = out_dir
        self._options = dict(options)
        self._merge_pdf = merge_pdf
        self._merge_kind = merge_kind
        self._cancel_event = threading.Event()
        self._notes: list[str] = []
        self._note_lock = threading.Lock()

    def cancel(self):
        self._cancel_event.set()

    # ------------------------------------------------------------

    def run(self):
        total = len(self._rows)

        if self._merge_pdf and self._target == "pdf":
            self._run_merge_pdf(total)
            return

        # Word COM 引擎不允许并行；其余按独立小任务并行
        parallel = 1 if self._options.get("use_word") else min(4, total)
        ok = 0
        bad = 0
        self.progress.emit(0, total)
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            futures = {pool.submit(self._convert_one, idx, path): idx
                       for idx, path in self._rows}
            done = 0
            for fut in as_completed(futures):
                ok += 1 if fut.result() else 0
                bad += 0 if fut.result() else 1
                done += 1
                self.progress.emit(done, total)

        notes = "；".join(self._notes)
        summary = f"完成 {ok} 个" if not bad else f"成功 {ok} 个，失败/跳过 {bad} 个"
        self.all_done.emit(ok, bad, notes if notes else summary)

    # ------------------------------------------------------------

    def _convert_one(self, idx: int, path: Path) -> bool:
        """转换单个文件；返回是否成功（取消按失败计，用于汇总）。"""
        if self._cancel_event.is_set():
            self.row_done.emit(idx, "skip", "已取消", [])
            return False
        self.row_started.emit(idx)
        try:
            result = registry.convert_file(path, self._target, self._out_dir, self._options)
            self.row_done.emit(idx, "ok", "；".join(str(o) for o in result.outputs),
                               [str(o) for o in result.outputs])
            if result.note:
                with self._note_lock:
                    self._notes.append(result.note)
            return True
        except ConvertCancelled:
            self.row_done.emit(idx, "skip", "已取消", [])
            return False
        except ConvertError as e:
            self.row_done.emit(idx, "fail", str(e), [])
            return False
        except Exception as e:  # 防御：任何异常都不应崩溃界面
            self.row_done.emit(idx, "fail", f"内部错误：{e}", [])
            return False

    def _run_merge_pdf(self, total: int):
        """多个输入合并为一个 PDF（图片合并 / PDF 合并），串行执行。"""
        paths = [p for _, p in self._rows]
        for idx, _ in self._rows:
            self.row_started.emit(idx)
        try:
            if self._merge_kind == "pdfs":
                result = registry.convert_pdfs_to_merged(
                    paths, self._out_dir or paths[0].parent, self._options)
            else:
                result = registry.convert_images_to_single_pdf(
                    paths, self._out_dir or paths[0].parent, self._options)
            for idx, _ in self._rows:
                self.row_done.emit(idx, "ok", str(result.outputs[0]),
                                   [str(o) for o in result.outputs])
            notes = result.note or ""
            self.progress.emit(total, total)
            self.all_done.emit(total, 0, notes)
        except ConvertError as e:
            for idx, _ in self._rows:
                self.row_done.emit(idx, "fail", str(e), [])
            self.progress.emit(total, total)
            self.all_done.emit(0, total, str(e))
