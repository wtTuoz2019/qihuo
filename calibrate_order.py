"""
标定下单按钮坐标（买入 / 卖出 / 确认）。

用法:
  python calibrate_order.py
"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("pip install pyyaml")
    sys.exit(1)


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def cursor_pos() -> tuple[int, int]:
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def ask_yes_no(prompt: str) -> bool:
    while True:
        ans = input(f"{prompt} [Y/n]: ").strip().lower()
        if ans in ("", "y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("  请输入 Y 或 N")


def pick_point(label: str, hint: str) -> list[int]:
    print(f"\n=== 标定 {label} ===")
    print(f"  {hint}")
    input("  鼠标移到按钮正中，按 Enter...")
    x, y = cursor_pos()
    print(f"  坐标: [{x}, {y}]")
    if ask_yes_no("  确认?"):
        return [x, y]
    return pick_point(label, hint)


def main() -> None:
    if sys.platform != "win32":
        print("请在 Windows 上运行")
        sys.exit(1)

    path = Path("config.yaml")
    if not path.exists():
        print("找不到 config.yaml")
        sys.exit(1)

    print("标定下单按钮。窗口不要移动。建议先在模拟盘练习。")
    print("默认点「模拟客户端」的买入/卖出。")
    input("准备好按 Enter...")

    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    trade = cfg.setdefault("trade", {})
    clicks = {}

    if ask_yes_no("标定 买入 按钮?"):
        clicks["buy"] = pick_point("buy", "模拟客户端 → 买入 / 买开 按钮中心")
    if ask_yes_no("标定 卖出 按钮?"):
        clicks["sell"] = pick_point("sell", "模拟客户端 → 卖出 / 卖开 按钮中心")
    if ask_yes_no("标定 确认 按钮?（无确认框选 N）"):
        clicks["confirm"] = pick_point("confirm", "下单确认弹窗的「确定」")

    if not clicks:
        print("未标定任何按钮")
        sys.exit(1)

    trade.setdefault("alert_spread", 5.0)
    trade.setdefault("order_spread", 5.0)
    trade.setdefault("auto_order", False)
    trade.setdefault("dry_run", True)
    trade.setdefault("software", "software_a")
    trade["clicks"] = {**(trade.get("clicks") or {}), **clicks}
    cfg["trade"] = trade
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print("\n✓ 已写入 config.yaml → trade.clicks")
    print("  真实下单前: auto_order: true  且  dry_run: false")
    print("  先保持 dry_run: true 看 logs/orders.log")


if __name__ == "__main__":
    main()
