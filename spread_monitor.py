"""
交易向实时价差监控 — UI 直读 + 屏幕区域 OCR 备用。

用法:
  copy config.example.yaml config.yaml
  python diagnose.py
  python calibrate_regions.py --target software_a
  python spread_monitor.py
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None

from alert import AlertConfig, AlertEngine
from quote_reader import (
    Quote,
    QuoteLabels,
    ReadStatus,
    RegionSet,
    SoftwareConfig,
    invalidate_cache,
    list_windows,
    read_quote,
)


@dataclass
class CompareConfig:
    mode: str = "executable"


@dataclass
class AppConfig:
    poll_interval_ms: int
    software_a: SoftwareConfig
    software_b: SoftwareConfig
    compare: CompareConfig
    alert: AlertConfig
    price_range: tuple[float, float] = (1000, 999999)
    log_every_tick: bool = False
    ocr: dict = field(default_factory=dict)


def load_config(path: Path) -> AppConfig:
    if yaml is None:
        raise RuntimeError("缺少 pyyaml")
    if not path.exists():
        raise FileNotFoundError(f"请先复制 config.example.yaml 为 {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    def labels(block: dict) -> QuoteLabels:
        lb = block.get("labels") or {}
        return QuoteLabels(
            bid=lb.get("bid", "买入"),
            ask=lb.get("ask", "卖出"),
            last=lb.get("last", ""),
        )

    def sw(key: str) -> SoftwareConfig:
        b = raw[key]
        return SoftwareConfig(
            window_title=b.get("window_title", ""),
            read_mode=b.get("read_mode", "auto"),
            labels=labels(b),
            bid_control_name=b.get("bid_control_name") or "",
            ask_control_name=b.get("ask_control_name") or "",
            last_control_name=b.get("last_control_name") or "",
            regions=RegionSet.from_dict(b.get("regions")),
        )

    alert_raw = raw.get("alert") or {}
    webhook = raw.get("webhook") or {}
    pr = raw.get("price_range") or [1000, 999999]

    alert = AlertConfig(
        tick_size=float(alert_raw.get("tick_size", 0.25)),
        spread_yuan=float(alert_raw.get("spread_yuan", 5.0)),
        confirm_reads=int(alert_raw.get("confirm_reads", 2)),
        cooldown_ms=int(alert_raw.get("cooldown_ms", 2000)),
        sound=bool(alert_raw.get("sound", True)),
        log_csv=str(alert_raw.get("log_csv", "spreads.csv")),
        log_txt=str(alert_raw.get("log_txt", "spreads.log")),
        webhook_enabled=bool(webhook.get("enabled", False)),
        webhook_url=str(webhook.get("url") or ""),
    )

    return AppConfig(
        poll_interval_ms=int(raw.get("poll_interval_ms", 50)),
        software_a=sw("software_a"),
        software_b=sw("software_b"),
        compare=CompareConfig(mode=(raw.get("compare") or {}).get("mode", "executable")),
        alert=alert,
        price_range=(float(pr[0]), float(pr[1])),
        log_every_tick=bool(raw.get("log_every_tick", False)),
        ocr=raw.get("ocr") or {},
    )


def _fmt(v: Optional[float]) -> str:
    return f"{v:.2f}" if v is not None else "  --  "


def build_snapshot(qa: Quote, qb: Quote, loop_latency_ms: float) -> dict:
    exec_ab = exec_ba = mid_spread = None

    if qa.bid is not None and qb.ask is not None:
        exec_ab = round(qa.bid - qb.ask, 2)
    if qb.bid is not None and qa.ask is not None:
        exec_ba = round(qb.bid - qa.ask, 2)

    ma, mb = qa.mid, qb.mid
    if ma is not None and mb is not None:
        mid_spread = round(ma - mb, 2)

    last_spread = None
    if qa.last is not None and qb.last is not None:
        last_spread = round(qa.last - qb.last, 2)
    elif mid_spread is not None:
        last_spread = mid_spread

    return {
        "a_bid": qa.bid, "a_ask": qa.ask, "a_last": qa.last,
        "b_bid": qb.bid, "b_ask": qb.ask, "b_last": qb.last,
        "exec_a_sell_b_buy": exec_ab,
        "exec_b_sell_a_buy": exec_ba,
        "mid_spread": mid_spread,
        "last_spread": last_spread,
        "latency_ms": round(loop_latency_ms, 1),
    }


def _explain_fail(name: str, cfg: SoftwareConfig, st: ReadStatus) -> str:
    parts = [f"{name}:"]
    if not st.window_found and cfg.read_mode != "region":
        parts.append(f"未找到含 {cfg.window_title!r} 的窗口")
    if st.error:
        parts.append(st.error)
    if cfg.read_mode in ("auto", "ui") and st.control_count == 0 and st.window_found:
        parts.append("窗口找到但无文本控件(自绘界面)，请用 calibrate_regions.py")
    if cfg.read_mode == "region" and not cfg.regions.any():
        parts.append("未标定 regions")
    parts.append(f"mode={st.mode_used or cfg.read_mode}")
    return " ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="双软件可执行价差监控")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    interval = cfg.poll_interval_ms / 1000.0
    engine = AlertEngine(cfg.alert)
    lo, hi = cfg.price_range

    from region_reader import init_ocr_from_config

    init_ocr_from_config(getattr(cfg, "ocr", None) or {})

    print("=" * 72)
    print("  实时价差监控 [交易模式]")
    print("=" * 72)
    print(f"  A: {cfg.software_a.window_title!r} mode={cfg.software_a.read_mode}")
    print(f"  B: {cfg.software_b.window_title!r} mode={cfg.software_b.read_mode}")
    print(f"  轮询: {cfg.poll_interval_ms} ms")
    print(f"  告警: |价差| >= {cfg.alert.spread_yuan:.0f} 点  声音={cfg.alert.sound}")
    from paths import log_path

    print(f"  日志目录: logs/")
    print(f"  日志: {log_path(cfg.alert.log_txt).name}  /  {log_path(cfg.alert.log_csv).name}")
    print("-" * 72)

    wins = list_windows()
    for key, title in [(cfg.software_a.window_title, "A"), (cfg.software_b.window_title, "B")]:
        hit = [w for w in wins if key in w]
        print(f"  窗口[{title}] 匹配: {hit if hit else '无 — 检查 window_title 或改用 region 模式'}")

    print("-" * 72)

    last_line = ""
    fail_count = 0
    warned_setup = False

    while True:
        t0 = time.perf_counter()

        qa, sta = read_quote(cfg.software_a, lo, hi)
        qb, stb = read_quote(cfg.software_b, lo, hi)

        loop_ms = (time.perf_counter() - t0) * 1000
        ts = datetime.now().strftime("%H:%M:%S.") + f"{datetime.now().microsecond // 1000:03d}"

        if not qa.valid() or not qb.valid():
            fail_count += 1
            if fail_count >= 20:
                invalidate_cache()
                fail_count = 0
            print(f"[{ts}] 读价失败 (loop {loop_ms:.0f}ms)")
            print(f"  {_explain_fail('A', cfg.software_a, sta)}")
            print(f"  {_explain_fail('B', cfg.software_b, stb)}")
            if not warned_setup:
                print("  >> 运行: python diagnose.py")
                print("  >> 标定: python calibrate_regions.py --target software_a")
                warned_setup = True
            if args.once:
                sys.exit(1)
            time.sleep(max(interval, 0.5))
            continue

        fail_count = 0
        snap = build_snapshot(qa, qb, loop_ms)

        exec_ab = snap["exec_a_sell_b_buy"]
        exec_ba = snap["exec_b_sell_a_buy"]
        mid = snap["mid_spread"]
        last_sp = snap["last_spread"]

        def _fmt_spread(v: Optional[float]) -> str:
            return f"{v:+.2f}" if v is not None else "  --  "

        line = (
            f"[{ts}] "
            f"A {_fmt(qa.bid)}/{_fmt(qa.ask)}/{_fmt(qa.last)} | "
            f"B {_fmt(qb.bid)}/{_fmt(qb.ask)}/{_fmt(qb.last)} | "
            f"价差 {_fmt_spread(last_sp)} Mid {_fmt_spread(mid)} | "
            f"AB {_fmt_spread(exec_ab)} BA {_fmt_spread(exec_ba)} | "
            f"{loop_ms:.0f}ms"
        )

        changed = line != last_line
        if changed:
            print(line)
            last_line = line
            engine.log_tick(snap)

        alerts = engine.evaluate(snap)
        for msg in alerts:
            print(f"\033[91m{msg}\033[0m")

        if args.once:
            break

        elapsed = time.perf_counter() - t0
        sleep_sec = max(0.0, interval - elapsed)
        if sleep_sec:
            time.sleep(sleep_sec)


if __name__ == "__main__":
    main()
