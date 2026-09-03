"""下单模块 — 默认 dry_run，只写日志不点鼠标。

真实点击需同时满足:
  trade.auto_order: true
  trade.dry_run: false
  已标定 clicks.buy / clicks.sell
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from paths import log_path


@dataclass
class ClickPoint:
    x: int = 0
    y: int = 0

    def valid(self) -> bool:
        return self.x > 0 and self.y > 0


@dataclass
class TradeConfig:
    alert_spread: float = 5.0
    order_spread: float = 5.0
    auto_order: bool = False
    dry_run: bool = True
    lots: int = 1
    cooldown_ms: int = 5000
    software: str = "software_a"
    window_title: str = "行情交易系统"
    buy: ClickPoint = field(default_factory=ClickPoint)
    sell: ClickPoint = field(default_factory=ClickPoint)
    confirm: ClickPoint = field(default_factory=ClickPoint)

    @classmethod
    def from_dict(cls, raw: dict | None, window_titles: dict[str, str] | None = None) -> "TradeConfig":
        raw = raw or {}
        clicks = raw.get("clicks") or {}
        software = str(raw.get("software", "software_a"))
        titles = window_titles or {}
        title = str(raw.get("window_title") or titles.get(software) or "")

        def pt(key: str) -> ClickPoint:
            arr = clicks.get(key) or [0, 0]
            if isinstance(arr, dict):
                return ClickPoint(int(arr.get("x", 0)), int(arr.get("y", 0)))
            if len(arr) >= 2:
                return ClickPoint(int(arr[0]), int(arr[1]))
            return ClickPoint()

        return cls(
            alert_spread=float(raw.get("alert_spread", 5.0)),
            order_spread=float(raw.get("order_spread", raw.get("alert_spread", 5.0))),
            auto_order=bool(raw.get("auto_order", False)),
            dry_run=bool(raw.get("dry_run", True)),
            lots=int(raw.get("lots", 1)),
            cooldown_ms=int(raw.get("cooldown_ms", 5000)),
            software=software,
            window_title=title,
            buy=pt("buy"),
            sell=pt("sell"),
            confirm=pt("confirm"),
        )


class OrderExecutor:
    def __init__(self, cfg: TradeConfig) -> None:
        self.cfg = cfg
        self._last_ts = 0.0
        self._log = log_path("orders.log")

    def _write(self, line: str) -> None:
        stamp = datetime.now().isoformat(timespec="milliseconds")
        with self._log.open("a", encoding="utf-8") as f:
            f.write(f"{stamp} {line}\n")

    def _cooldown_ok(self) -> bool:
        return (time.perf_counter() - self._last_ts) * 1000 >= self.cfg.cooldown_ms

    def decide_side(self, last_spread: Optional[float]) -> Optional[str]:
        """A 高于 B → 在 A 卖；B 高于 A → 在 A 买。默认在 software_a 下单。"""
        if last_spread is None:
            return None
        if last_spread >= self.cfg.order_spread:
            return "sell"
        if last_spread <= -self.cfg.order_spread:
            return "buy"
        return None

    def maybe_order(self, snap: dict) -> Optional[str]:
        if not self.cfg.auto_order:
            return None
        if not self._cooldown_ok():
            return None

        signed = snap.get("last_spread")
        if signed is None:
            signed = snap.get("mid_spread")
        side = self.decide_side(signed if signed is None else float(signed))
        if side is None:
            return None

        self._last_ts = time.perf_counter()
        point = self.cfg.buy if side == "buy" else self.cfg.sell
        action = f"{side.upper()} lots={self.cfg.lots} spread={signed} target={self.cfg.software}"

        if self.cfg.dry_run or not point.valid():
            reason = "dry_run" if self.cfg.dry_run else "未标定点击坐标"
            msg = f"ORDER_SKIP {reason} {action}"
            self._write(msg)
            return msg

        try:
            from win_input import click_xy, foreground_by_title
        except Exception as exc:
            msg = f"ORDER_FAIL 无法加载 win_input: {exc}"
            self._write(msg)
            return msg

        if self.cfg.window_title:
            foreground_by_title(self.cfg.window_title)
        click_xy(point.x, point.y)
        if self.cfg.confirm.valid():
            time.sleep(0.12)
            click_xy(self.cfg.confirm.x, self.cfg.confirm.y)

        msg = f"ORDER_CLICK {action} xy=({point.x},{point.y})"
        self._write(msg)
        return msg
