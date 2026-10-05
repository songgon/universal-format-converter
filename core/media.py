"""音视频转换模块：调用 ffmpeg（自动探测内置 / PATH / 环境变量）。"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from functools import lru_cache
from pathlib import Path

from .utils import ConvertCancelled, ConvertError, safe_output_path

AUDIO_INPUTS = {"mp3", "wav", "flac", "m4a", "aac", "ogg", "opus", "wma", "aiff", "ape", "amr"}
VIDEO_INPUTS = {"mp4", "mkv", "avi", "mov", "webm", "wmv", "flv", "m4v", "ts", "mpg", "mpeg", "3gp"}

AUDIO_TARGETS = [
    ("mp3", "MP3 音频"), ("wav", "WAV 音频"), ("flac", "FLAC 无损"),
    ("m4a", "M4A 音频"), ("aac", "AAC 音频"), ("ogg", "OGG 音频"),
    ("opus", "Opus 音频"), ("wma", "WMA 音频"),
]
VIDEO_TARGETS = [
    ("mp4", "MP4 视频"), ("mkv", "MKV 视频"), ("mov", "MOV 视频"),
    ("webm", "WebM 视频"), ("avi", "AVI 视频"), ("wmv", "WMV 视频"),
    ("gif", "GIF 动图（视频截取）"),
]
TARGETS = AUDIO_TARGETS + VIDEO_TARGETS

# 各目标的 ffmpeg 参数（标准档）
_CODEC = {
    "mp3": ["-c:a", "libmp3lame", "-b:a", "192k"],
    "wav": ["-c:a", "pcm_s16le"],
    "flac": ["-c:a", "flac"],
    "m4a": ["-c:a", "aac", "-b:a", "192k"],
    "aac": ["-c:a", "aac", "-b:a", "192k"],
    "ogg": ["-c:a", "libvorbis", "-q:a", "5"],
    "opus": ["-c:a", "libopus", "-b:a", "160k"],
    "wma": ["-c:a", "wmav2", "-b:a", "192k"],
    "mp4": ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    "mkv": ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-b:a", "192k"],
    "mov": ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p"],
    "webm": ["-c:v", "libvpx-vp9", "-crf", "40", "-b:v", "0", "-c:a", "libopus"],
    "avi": ["-c:v", "mpeg4", "-q:v", "5", "-c:a", "libmp3lame", "-b:a", "192k"],
    "wmv": ["-c:v", "wmv2", "-q:v", "5", "-c:a", "wmav2", "-b:a", "192k"],
    "gif": ["-vf", "fps=12,scale=480:-2:flags=lanczos", "-loop", "0"],
}

# 最高档：音频拉满码率，视频用接近视觉无损的 CRF；无损格式（wav/flac）本就无损
_CODEC_MAX = {
    "mp3": ["-c:a", "libmp3lame", "-b:a", "320k"],
    "wav": _CODEC["wav"],
    "flac": _CODEC["flac"],
    "m4a": ["-c:a", "aac", "-b:a", "320k"],
    "aac": ["-c:a", "aac", "-b:a", "320k"],
    "ogg": ["-c:a", "libvorbis", "-q:a", "9"],
    "opus": ["-c:a", "libopus", "-b:a", "256k"],
    "wma": _CODEC["wma"],
    "mp4": ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-c:a", "aac", "-b:a", "320k", "-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    "mkv": ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-c:a", "aac", "-b:a", "320k"],
    "mov": ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-c:a", "aac", "-b:a", "320k", "-pix_fmt", "yuv420p"],
    "webm": ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0", "-row-mt", "1", "-c:a", "libopus", "-b:a", "256k"],
    "avi": ["-c:v", "mpeg4", "-q:v", "2", "-c:a", "libmp3lame", "-b:a", "320k"],
    "wmv": _CODEC["wmv"],
    "gif": _CODEC["gif"],
}


VIDEO_TARGETS_DICT = dict(VIDEO_TARGETS)


def can_convert(src_ext: str, dst_ext: str) -> bool:
    if not is_available():
        return False
    src_ok = src_ext in AUDIO_INPUTS or src_ext in VIDEO_INPUTS
    dst_ok = dst_ext in {t for t, _ in TARGETS}
    if src_ext in AUDIO_INPUTS and dst_ext in VIDEO_TARGETS_DICT:
        return False  # 音频转不了视频/GIF
    return src_ok and dst_ok


def is_available() -> bool:
    return ffmpeg_path() is not None


@lru_cache(maxsize=1)
def ffmpeg_path() -> str | None:
    env = os.environ.get("FFMPEG_PATH")
    if env and Path(env).exists():
        return env
    # 打包为 exe 后：tools 位于 exe 同级目录
    exe_dir = Path(sys.executable).parent
    bundled = exe_dir / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
    if bundled.exists():
        return str(bundled)
    bundled = Path(__file__).resolve().parent.parent / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
    if bundled.exists():
        return str(bundled)
    return shutil.which("ffmpeg")


# H.265 编码（体积更小约 30%，兼容性稍差；essentials 构建含 libx265）
_CODEC_MAX_H265 = {
    "mp4": ["-c:v", "libx265", "-preset", "slow", "-crf", "24", "-tag:v", "hvc1",
            "-c:a", "aac", "-b:a", "320k", "-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    "mkv": ["-c:v", "libx265", "-preset", "slow", "-crf", "24", "-c:a", "aac", "-b:a", "320k"],
    "mov": ["-c:v", "libx265", "-preset", "slow", "-crf", "24", "-tag:v", "hvc1",
            "-c:a", "aac", "-b:a", "320k", "-pix_fmt", "yuv420p"],
}
_CODEC_NORMAL_H265 = {
    "mp4": ["-c:v", "libx265", "-preset", "medium", "-crf", "26", "-tag:v", "hvc1",
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    "mkv": ["-c:v", "libx265", "-preset", "medium", "-crf", "26", "-c:a", "aac", "-b:a", "192k"],
    "mov": ["-c:v", "libx265", "-preset", "medium", "-crf", "26", "-tag:v", "hvc1",
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p"],
}


def convert(src: Path, target: str, out_dir: Path | None, options: dict) -> list[Path]:
    ff = ffmpeg_path()
    if not ff:
        raise ConvertError("未找到 ffmpeg，无法转换音视频（见 README 的安装说明）")
    dst = safe_output_path(src, out_dir, target, options.get("overwrite", False))
    level = options.get("media_level", "max")
    codec_table = _CODEC_MAX if level == "max" else _CODEC
    if options.get("vcodec") == "h265" and target in _CODEC_MAX_H265:
        codec_table = _CODEC_MAX_H265 if level == "max" else _CODEC_NORMAL_H265
    cmd = [ff, "-y", "-i", str(src)]
    cmd += codec_table.get(target, [])
    cmd += [str(dst)]

    cancel_event = options.get("cancel_event")
    creation = 0x08000000  # CREATE_NO_WINDOW，不闪黑框
    # stderr 写临时文件而不是管道：ffmpeg 输出量大，管道不读会阻塞进程
    with tempfile.TemporaryFile() as errf:
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=errf,
                                    creationflags=creation)
        except OSError as e:
            raise ConvertError(f"无法启动 ffmpeg：{e}") from e
        deadline = time.time() + 3600
        while True:
            if cancel_event is not None and cancel_event.is_set():
                proc.kill()
                proc.wait()
                raise ConvertCancelled("已取消")
            try:
                proc.wait(timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                pass
            if time.time() > deadline:
                proc.kill()
                proc.wait()
                raise ConvertError("转换超时（超过 60 分钟）")
        errf.seek(0)
        stderr_text = errf.read().decode("utf-8", errors="replace")

    if proc.returncode != 0 or not dst.exists():
        tail = stderr_text.strip().splitlines()[-6:]
        raise ConvertError("ffmpeg 转换失败：" + ("；".join(tail) or "未知错误"))
    return [dst]


def category_label(src_ext: str) -> str:
    if src_ext in AUDIO_INPUTS:
        return "音频"
    if src_ext in VIDEO_INPUTS:
        return "视频"
    return "音视频"
