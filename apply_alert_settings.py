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
    trade.setdefault("order_spread", 5.0)
    trade.setdefault("auto_order", False)
    trade.setdefault("dry_run", True)
    trade.setdefault("lots", 1)
    trade.setdefault("software", "software_a")
    cfg["trade"] = trade
    CONFIG.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print("✓ 已写入告警/下单设置（regions 与 clicks 未覆盖）")
    print(f"  改阈值: 编辑 config.yaml → trade.alert_spread / trade.order_spread")
    print("  下单标定: python calibrate_order.py")
    print("下一步: python spread_monitor.py")


if __name__ == "__main__":
    main()
