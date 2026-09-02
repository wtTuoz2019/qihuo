"""Windows UI 行情读取 — 支持控件缓存，降低轮询延迟。"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import uiautomation as auto
except ImportError:
    auto = None

if auto is not None:
    auto.SetGlobalSearchTimeout(0.25)

PRICE_STRICT_RE = re.compile(r"^\d{4,6}(?:\.\d{1,2})?$")
MAX_CONTROLS = 400


@dataclass
class QuoteLabels:
    bid: str = "买入"
    ask: str = "卖出"
    last: str = ""


@dataclass
class SoftwareConfig:
    window_title: str
    labels: QuoteLabels = field(default_factory=QuoteLabels)
    bid_control_name: str = ""
    ask_control_name: str = ""
    last_control_name: str = ""


@dataclass
class Quote:
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    ts: float = 0.0

    @property
    def mid(self) -> Optional[float]:
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2
        return self.last

    def valid(self) -> bool:
        return any(v is not None for v in (self.bid, self.ask, self.last))


@dataclass
class _WindowCache:
    window_keyword: str
    window_ref: object | None = None
    controls_flat: list | None = None
    controls_ts: float = 0.0
    label_index: dict[str, list[int]] = field(default_factory=dict)


_CACHE: dict[str, _WindowCache] = {}
CONTROLS_TTL_SEC = 3.0


def find_window(keyword: str):
    if auto is None:
        raise RuntimeError("uiautomation 未安装")
    root = auto.GetRootControl()
    for win in root.GetChildren():
        title = win.Name or ""
        if keyword in title and win.ControlTypeName == "WindowControl":
            return win
    return None


def control_text(control) -> str:
    name = (control.Name or "").strip()
    if name:
        return name
    try:
        return (control.GetLegacyIAccessiblePattern().Value or "").strip()
    except Exception:
        return ""


def iter_controls(control, max_depth: int = 14, depth: int = 0):
    if depth > max_depth:
        return
    yield control
    try:
        for child in control.GetChildren():
            yield from iter_controls(child, max_depth, depth + 1)
    except Exception:
        return


def _get_flat_controls(keyword: str, win) -> list:
    cache = _CACHE.setdefault(keyword, _WindowCache(window_keyword=keyword))
    now = time.perf_counter()
    if cache.controls_flat and (now - cache.controls_ts) < CONTROLS_TTL_SEC:
        return cache.controls_flat

    flat: list = []
    for ctrl in iter_controls(win):
        flat.append(ctrl)
        if len(flat) >= MAX_CONTROLS:
            break
    cache.controls_flat = flat
    cache.controls_ts = now
    cache.label_index.clear()
    for i, ctrl in enumerate(flat):
        text = control_text(ctrl)
        if not text:
            continue
        for token in (text,):
            cache.label_index.setdefault(token, []).append(i)
            if len(text) <= 8:
                for part in text.split():
                    cache.label_index.setdefault(part, []).append(i)
    return flat


def _parse_price(text: str) -> Optional[float]:
    text = text.strip()
    if PRICE_STRICT_RE.match(text):
        return float(text)
    return None


def _read_by_name(flat: list, name: str) -> Optional[float]:
    for ctrl in flat:
        if control_text(ctrl) == name:
            return _parse_price(control_text(ctrl))
    return None


def _read_near_label(flat: list, label: str, lookahead: int = 14) -> Optional[float]:
    for i, ctrl in enumerate(flat):
        text = control_text(ctrl)
        if label not in text:
            continue
        for j in range(i, min(i + lookahead, len(flat))):
            val = _parse_price(control_text(flat[j]))
            if val is not None:
                return val
    return None


def _read_dominant_last(flat: list, lo: float = 1000, hi: float = 999999) -> Optional[float]:
    from collections import Counter

    vals: list[float] = []
    for ctrl in flat:
        val = _parse_price(control_text(ctrl))
        if val is not None and lo < val < hi:
            vals.append(val)
    if not vals:
        return None
    return Counter(vals).most_common(1)[0][0]


def read_quote(cfg: SoftwareConfig, price_lo: float = 1000, price_hi: float = 999999) -> Quote:
    win = find_window(cfg.window_title)
    if not win:
        return Quote(ts=time.perf_counter())

    flat = _get_flat_controls(cfg.window_title, win)
    labels = cfg.labels

    bid = _read_by_name(flat, cfg.bid_control_name) if cfg.bid_control_name else None
    ask = _read_by_name(flat, cfg.ask_control_name) if cfg.ask_control_name else None
    last = _read_by_name(flat, cfg.last_control_name) if cfg.last_control_name else None

    if bid is None and labels.bid:
        bid = _read_near_label(flat, labels.bid)
    if ask is None and labels.ask:
        ask = _read_near_label(flat, labels.ask)
    if last is None and labels.last:
        last = _read_near_label(flat, labels.last)

    if last is None:
        last = _read_dominant_last(flat, price_lo, price_hi)

    return Quote(bid=bid, ask=ask, last=last, ts=time.perf_counter())


def invalidate_cache(keyword: str = "") -> None:
    if keyword:
        _CACHE.pop(keyword, None)
    else:
        _CACHE.clear()
