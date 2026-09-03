"""统一读价：UI 控件 / 屏幕区域。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal, Optional

try:
    import uiautomation as auto

    auto.SetGlobalSearchTimeout(0.25)
except Exception:
    auto = None

from region_reader import RegionSet, read_regions
from ui_reader import (
    Quote,
    QuoteLabels,
    SoftwareConfig as UiSoftwareConfig,
    find_window,
    invalidate_cache,
    read_quote as read_quote_ui,
)

ReadMode = Literal["auto", "ui", "region"]


@dataclass
class SoftwareConfig:
    window_title: str
    read_mode: ReadMode = "auto"
    labels: QuoteLabels = field(default_factory=QuoteLabels)
    bid_control_name: str = ""
    ask_control_name: str = ""
    last_control_name: str = ""
    regions: RegionSet = field(default_factory=RegionSet)


@dataclass
class ReadStatus:
    window_found: bool = False
    window_title: str = ""
    mode_used: str = ""
    control_count: int = 0
    error: str = ""


def list_windows() -> list[str]:
    if auto is None:
        return []
    titles: list[str] = []
    try:
        root = auto.GetRootControl()
        for win in root.GetChildren():
            try:
                if win.ControlTypeName == "WindowControl" and win.Name:
                    titles.append(win.Name)
            except Exception:
                continue
    except Exception:
        return titles
    return titles


def read_quote(cfg: SoftwareConfig, lo: float, hi: float) -> tuple[Quote, ReadStatus]:
    status = ReadStatus()

    mode = cfg.read_mode
    if mode == "auto":
        mode = "region" if cfg.regions.any() else "ui"

    # region 模式不碰 UIAutomation，避免 COM「拒绝访问」把进程打崩
    if mode == "region":
        status.mode_used = "region"
        if not cfg.regions.any():
            status.error = "read_mode=region 但未配置 regions，请先运行 calibrate_regions.py"
            return Quote(ts=time.perf_counter()), status
        try:
            bid, ask, last = read_regions(cfg.regions, lo, hi)
            status.window_found = True
            return Quote(bid=bid, ask=ask, last=last, ts=time.perf_counter()), status
        except Exception as exc:
            status.error = str(exc)
            return Quote(ts=time.perf_counter()), status

    win = None
    try:
        win = find_window(cfg.window_title) if cfg.window_title else None
        status.window_found = win is not None
        if win is not None:
            try:
                status.window_title = win.Name or ""
            except Exception:
                status.window_title = cfg.window_title
    except Exception as exc:
        status.error = f"find_window: {exc}"

    ui_cfg = UiSoftwareConfig(
        window_title=cfg.window_title,
        labels=cfg.labels,
        bid_control_name=cfg.bid_control_name,
        ask_control_name=cfg.ask_control_name,
        last_control_name=cfg.last_control_name,
    )

    # UI 模式
    try:
        q = read_quote_ui(ui_cfg, lo, hi)
        status.mode_used = "ui"
        if win is not None:
            from ui_reader import _CACHE

            cache = _CACHE.get(cfg.window_title)
            status.control_count = len(cache.controls_flat) if cache and cache.controls_flat else 0
        if not q.valid() and cfg.regions.any():
            bid, ask, last = read_regions(cfg.regions, lo, hi)
            q = Quote(bid=bid or q.bid, ask=ask or q.ask, last=last or q.last, ts=time.perf_counter())
            status.mode_used = "ui->region_fallback"
        return q, status
    except Exception as exc:
        status.error = str(exc)
        if cfg.regions.any():
            try:
                bid, ask, last = read_regions(cfg.regions, lo, hi)
                status.mode_used = "region_fallback"
                return Quote(bid=bid, ask=ask, last=last, ts=time.perf_counter()), status
            except Exception as exc2:
                status.error = f"{exc}; fallback: {exc2}"
        return Quote(ts=time.perf_counter()), status


__all__ = [
    "SoftwareConfig",
    "Quote",
    "QuoteLabels",
    "ReadStatus",
    "read_quote",
    "list_windows",
    "invalidate_cache",
]
