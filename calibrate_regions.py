"""
标定屏幕价格区域 — 在 Windows 上运行。

用法:
  python calibrate_regions.py --target software_a
  python calibrate_regions.py --target software_b

说明:
  只需输入 y 然后回车，或 n 跳过。不要输入其他命令。
"""

from __future__ import annotations

import argparse
import ctypes
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("请先安装: python -m pip install pyyaml")
    sys.exit(1)

FIELD_HINT = {
    "software_a": {
        "bid": "模拟客户端 → 右侧「买入」价格数字",
        "ask": "模拟客户端 → 右侧「卖出」价格数字",
        "last": "模拟客户端 → 最新价（可选，一般 bid+ask 够用）",
    },
    "software_b": {
        "bid": "同花顺 → 右侧「买价」数字",
        "ask": "同花顺 → 右侧「卖价」数字",
        "last": "同花顺 → 顶部大字号最新价（可选）",
    },
}


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
        print("  请输入 Y 或直接回车=是，N=否（不要输入其他命令）")


def pick_region(label: str, hint: str) -> list[int] | None:
    print(f"\n{'=' * 50}")
    print(f"  标定: {label}")
    print(f"  位置: {hint}")
    print(f"{'=' * 50}")
    print("  ① 用鼠标把光标移到价格数字的【左上角】")
    input("  ② 移好后，只按一次 Enter...")
    x1, y1 = cursor_pos()
    print(f"     已记录左上: ({x1}, {y1})")
    print("  ③ 用鼠标把光标移到价格数字的【右下角】")
    input("  ④ 移好后，只按一次 Enter...")
    x2, y2 = cursor_pos()
    print(f"     已记录右下: ({x2}, {y2})")

    region = [min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)]
    w, h = region[2], region[3]
    print(f"     区域 [x,y,w,h] = {region}")

    if w < 15 or h < 8:
        print("  ✗ 区域太小，请重新标定（只框住数字，宽大约 80~150 像素）")
        return pick_region(label, hint)

    if ask_yes_no("  确认这个区域?"):
        return region
    return pick_region(label, hint)


def main() -> None:
    if sys.platform != "win32":
        print("请在 Windows 上运行")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="标定价格屏幕区域")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--target", choices=["software_a", "software_b"], required=True)
    args = parser.parse_args()

    path = Path(args.config)
    if not path.exists():
        print(f"找不到 {path}，请先: copy config.example.yaml config.yaml")
        sys.exit(1)

    hints = FIELD_HINT[args.target]
    name = "模拟客户端(行情交易系统)" if args.target == "software_a" else "同花顺期货通"

    print()
    print("=" * 50)
    print(f"  标定目标: {name}")
    print("=" * 50)
    print("  准备工作:")
    print("  1. 两个期货软件都已打开，价格清晰可见")
    print("  2. 窗口不要被其他窗口挡住")
    print("  3. 下面每个问题只按 Y+Enter 或 N+Enter")
    print("  4. 建议至少标定 bid 和 ask")
    print()
    input("  准备好了按 Enter 开始...")

    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    block = cfg.setdefault(args.target, {})
    block["read_mode"] = "region"

    regions: dict[str, list[int]] = {}
    for field in ("bid", "ask", "last"):
        if ask_yes_no(f"\n是否标定 {field}?  ({hints[field]})"):
            picked = pick_region(field, hints[field])
            if picked:
                regions[field] = picked

    if not regions:
        print("\n✗ 没有标定任何区域，config.yaml 未修改")
        print("  请重新运行本脚本，至少标定 bid 和 ask")
        sys.exit(1)

    block["regions"] = regions
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")

    print(f"\n✓ 已保存 {len(regions)} 个区域到 {path}")
    for k, v in regions.items():
        print(f"    {k}: {v}")
    print("\n下一步:")
    print(f"  python diagnose.py          # 测试读价")
    if args.target == "software_a":
        print("  python calibrate_regions.py --target software_b")
    else:
        print("  python spread_monitor.py    # 启动监控")


if __name__ == "__main__":
    main()
