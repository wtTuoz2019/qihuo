"""把 Windows 本地 config.yaml 改成：价差 5 点告警 + 声音 + 日志。标定坐标不会被覆盖。"""

from __future__ import annotations

from pathlib import Path

try:
    import yaml
except ImportError:
    print("pip install pyyaml")
    raise SystemExit(1)

CONFIG = Path("config.yaml")


def main() -> None:
    if not CONFIG.exists():
        print("找不到 config.yaml")
        raise SystemExit(1)

    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    cfg["log_every_tick"] = True
    ocr = cfg.get("ocr") or {}
    ocr.setdefault("engine", "easyocr")
    cfg["ocr"] = ocr
    alert = cfg.get("alert") or {}
    alert["confirm_reads"] = 2
    alert["cooldown_ms"] = 2000
    alert["sound"] = True
    alert["log_csv"] = "spreads.csv"
    alert["log_txt"] = "spreads.log"
    cfg["alert"] = alert
    trade = cfg.get("trade") or {}
    trade.setdefault("alert_spread", 5.0)
    trade.setdefault("open_long_spread", 5.0)
    trade.setdefault("open_short_spread", -5.0)
    trade.setdefault("leader", "software_b")
    trade.setdefault("order_on", "software_a")
    trade.setdefault("auto_order", False)
    trade.setdefault("dry_run", True)
    trade.setdefault("lots", 1)
    cfg["trade"] = trade
    CONFIG.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print("✓ 已写入：同花顺领先 → 模拟客户端跟单")
    print("  lead=同花顺-模拟  >=5开多  <=-5开空")
    print("  改阈值: config.yaml → trade.open_long_spread / open_short_spread")
    print("下一步: python spread_monitor.py")


if __name__ == "__main__":
    main()
