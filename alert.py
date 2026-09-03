"""交易向价差告警 — 声音、CSV、可读日志。"""

from __future__ import annotations

import csv
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime

from paths import log_path

try:
    import requests
except ImportError:
    requests = None


@dataclass
class AlertConfig:
    tick_size: float = 0.25
    spread_yuan: float = 5.0  # |价差| >= 此值（点/元）即告警
    confirm_reads: int = 2
    cooldown_ms: int = 2000
    sound: bool = True
    log_csv: str = "spreads.csv"
    log_txt: str = "spreads.log"
    webhook_enabled: bool = False
    webhook_url: str = ""


class AlertEngine:
    def __init__(self, cfg: AlertConfig) -> None:
        self.cfg = cfg
        self._streak: dict[str, int] = {}
        self._last_alert: dict[str, float] = {}
        self._log_path = log_path(cfg.log_csv)
        self._txt_path = log_path(cfg.log_txt)
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
                "lead_spread", "last_spread", "mid_spread",
                "exec_a_sell_b_buy", "exec_b_sell_a_buy",
                "latency_ms",
            ])

    def _beep(self, urgent: bool = True) -> None:
        if not self.cfg.sound or sys.platform != "win32":
            return

        def _play() -> None:
            try:
                import winsound

                if urgent:
                    for _ in range(3):
                        winsound.Beep(1500, 250)
                        time.sleep(0.08)
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
        now = datetime.now()
        iso = now.isoformat(timespec="milliseconds")
        with self._log_path.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                iso, event,
                snap.get("a_bid"), snap.get("a_ask"), snap.get("a_last"),
                snap.get("b_bid"), snap.get("b_ask"), snap.get("b_last"),
                snap.get("lead_spread"), snap.get("last_spread"), snap.get("mid_spread"),
                snap.get("exec_a_sell_b_buy"), snap.get("exec_b_sell_a_buy"),
                snap.get("latency_ms"),
            ])

        line = (
            f"{iso} {event}"
            f" 模拟={snap.get('a_last')} 同花顺={snap.get('b_last')}"
            f" 领先差={snap.get('lead_spread')}"
            f" Mid={snap.get('mid_spread')}"
            f" AB={snap.get('exec_a_sell_b_buy')} BA={snap.get('exec_b_sell_a_buy')}\n"
        )
        with self._txt_path.open("a", encoding="utf-8") as f:
            f.write(line)

    def _webhook(self, payload: dict) -> None:
        if not self.cfg.webhook_enabled or not self.cfg.webhook_url or not requests:
            return

        def _post() -> None:
            try:
                requests.post(self.cfg.webhook_url, json=payload, timeout=0.8)
            except Exception:
                pass

        threading.Thread(target=_post, daemon=True).start()

    def _main_spread(self, snap: dict) -> float | None:
        if snap.get("lead_spread") is not None:
            return abs(float(snap["lead_spread"]))
        if snap.get("last_spread") is not None:
            return abs(float(snap["last_spread"]))
        if snap.get("mid_spread") is not None:
            return abs(float(snap["mid_spread"]))
        return None

    def evaluate(self, snap: dict) -> list[str]:
        messages: list[str] = []
        th = self.cfg.spread_yuan
        spread = self._main_spread(snap)
        lead = snap.get("lead_spread")
        if lead is None:
            signed = snap.get("last_spread")
            if signed is None:
                signed = snap.get("mid_spread")
            lead = -float(signed) if signed is not None else None
        else:
            lead = float(lead)

        cond = spread is not None and spread >= th
        if not self._streak_hit("abs_spread", cond):
            return messages
        if not self._cooldown_ok("abs_spread"):
            return messages

        if lead is not None and lead >= 0:
            direction = "同花顺领先(偏多)"
        else:
            direction = "同花顺落后(偏空)"
        msg = f"【告警】领先差 {lead:+.2f}（同花顺-模拟，|{spread:.2f}| >= {th:.0f}）{direction}"
        messages.append(msg)
        self._mark_alert("abs_spread")
        self._log_row("ALERT", snap)
        self._webhook({"type": "alert", "lead_spread": lead, "abs": spread, **snap})
        self._beep(urgent=True)
        return messages

    def log_tick(self, snap: dict) -> None:
        self._log_row("TICK", snap)
