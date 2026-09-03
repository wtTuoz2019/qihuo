"""项目目录约定：代码在根目录，运行产物一律进 logs/。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"


def ensure_log_dir() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR


def log_path(name: str) -> Path:
    ensure_log_dir()
    p = Path(name)
    if p.is_absolute():
        return p
    if p.parent != Path("."):
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    return LOG_DIR / p.name
