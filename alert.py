"""交易向价差告警 — 声音、日志、Webhook。"""

from __future__ import annotations

import csv
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None


@dataclass
class AlertConfig:
    tick_size: float = 0.25
    # 可执行价差阈值（tick 数）。NQ 迷你纳指最小变动 0.25
    open_a_sell_b_buy_ticks: float = 1.0   # A_bid - B_ask >= N tick → 在 A 卖、在 B 买
    open_b_sell_a_buy_ticks: float = 1.0   # B_bid - A_ask >= N tick
    mid_spread_ticks: float = 0.0          # |mid_A - mid_B| 超过则提示（0=关闭）
    confirm_reads: int = 1                 # 连续 N 次满足才告警，1=最敏感
    cooldown_ms: int = 800                 # 同方向告警冷却
    sound: bool = True
    log_csv: str = "spreads.csv"
    webhook_enabled: bool = False
    webhook_url: str = ""


class AlertEngine:
    def __init__(self, cfg: AlertConfig) -> None:
        self.cfg = cfg
        self._streak: dict[str, int] = {}
        self._last_alert: dict[str, float] = {}
        self._log_path = Path(cfg.log_csv)
        self._ensure_csv()

    def _ensure_csv(self) -> None:
        if self._log_path.exists():
            return
        with self._log_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "datetime", "event",
                "a_bid", "a_ask", "a_last",
                "b_bid", "b_ask", "b_last",
                "exec_a_sell_b_buy", "exec_b_sell_a_buy", "mid_spread",
                "latency_ms",
            ])

    def _tick_threshold(self, ticks: float) -> float:
        return ticks * self.cfg.tick_size

    def _beep(self, urgent: bool = False) -> None:
        if not self.cfg.sound or sys.platform != "win32":
            return

        def _play() -> None:
            try:
                import winsound

                if urgent:
                    for freq in (1200, 1600, 1200):
                        winsound.Beep(freq, 120)
                        time.sleep(0.02)
                else:
                    winsound.Beep(1000, 180)
            except Exception:
                print("\a", end="", flush=True)

        threading.Thread(target=_play, daemon=True).start()

    def _cooldown_ok(self, key: str) -> bool:
        last = self._last_alert.get(key, 0.0)
        return (time.perf_counter() - last) * 1000 >= self.cfg.cooldown_ms

    def _mark_alert(self, key: str) -> None:
        self._last_alert[key] = time.perf_counter()

    def _streak_hit(self, key: str, cond: bool) -> bool:
        if cond:
            self._streak[key] = self._streak.get(key, 0) + 1
        else:
            self._streak[key] = 0
        return self._streak[key] >= self.cfg.confirm_reads

    def _log_row(self, event: str, snap: dict) -> None:
        with self._log_path.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                datetime.now().isoformat(timespec="milliseconds"),
                event,
                snap.get("a_bid"), snap.get("a_ask"), snap.get("a_last"),
                snap.get("b_bid"), snap.get("b_ask"), snap.get("b_last"),
                snap.get("exec_a_sell_b_buy"), snap.get("exec_b_sell_a_buy"),
                snap.get("mid_spread"), snap.get("latency_ms"),
            ])

    def _webhook(self, payload: dict) -> None:
        if not self.cfg.webhook_enabled or not self.cfg.webhook_url or not requests:
            return

        def _post() -> None:
            try:
                requests.post(self.cfg.webhook_url, json=payload, timeout=0.8)
            except Exception:
                pass

        threading.Thread(target=_post, daemon=True).start()

    def evaluate(self, snap: dict) -> list[str]:
        """返回本轮触发的告警文案。"""
        messages: list[str] = []
        exec_ab = snap.get("exec_a_sell_b_buy")
        exec_ba = snap.get("exec_b_sell_a_buy")
        mid = snap.get("mid_spread")

        th_ab = self._tick_threshold(self.cfg.open_a_sell_b_buy_ticks)
        th_ba = self._tick_threshold(self.cfg.open_b_sell_a_buy_ticks)
        th_mid = self._tick_threshold(self.cfg.mid_spread_ticks) if self.cfg.mid_spread_ticks > 0 else None

        checks = []
        if exec_ab is not None:
            checks.append(("A卖B买", "exec_ab", exec_ab, exec_ab >= th_ab, th_ab))
        if exec_ba is not None:
            checks.append(("B卖A买", "exec_ba", exec_ba, exec_ba >= th_ba, th_ba))
        if th_mid and mid is not None:
            checks.append(("Mid偏离", "mid", abs(mid), abs(mid) >= th_mid, th_mid))

        urgent = False
        for label, key, value, raw_cond, th in checks:
            if not self._streak_hit(key, raw_cond):
                continue
            if not self._cooldown_ok(key):
                continue

            ticks = value / self.cfg.tick_size
            th_ticks = th / self.cfg.tick_size
            msg = f"【告警】{label} 可执行价差 {value:+.2f} ({ticks:.1f} tick >= {th_ticks:.1f} tick)"
            messages.append(msg)
            self._mark_alert(key)
            self._log_row(f"ALERT_{key}", snap)
            self._webhook({"type": "alert", "label": label, "value": value, **snap})
            if label in ("A卖B买", "B卖A买"):
                urgent = True

        if messages:
            self._beep(urgent=urgent)

        return messages

    def log_tick(self, snap: dict) -> None:
        self._log_row("TICK", snap)
