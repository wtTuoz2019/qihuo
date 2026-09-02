"""
在 Windows 上运行，帮助定位两个软件窗口里的 UI 控件。

用法:
  python discover_ui.py
  python discover_ui.py --window "行情交易系统"
  python discover_ui.py --window "同花顺" --depth 15
"""

from __future__ import annotations

import argparse
import re
import sys

try:
    import uiautomation as auto
except ImportError:
    print("请先安装: pip install uiautomation")
    sys.exit(1)

PRICE_RE = re.compile(r"^\d{1,6}(?:\.\d+)?$")


def walk(control, depth: int, max_depth: int, lines: list[str], prefix: str = "") -> None:
    if depth > max_depth:
        return
    try:
        name = (control.Name or "").strip()
        ctype = control.ControlTypeName
        value = ""
        try:
            value = (control.GetLegacyIAccessiblePattern().Value or "").strip()
        except Exception:
            pass

        text = name or value
        if text and (PRICE_RE.match(text) or len(text) <= 30):
            marker = "  <-- 可能是价格" if PRICE_RE.match(text) else ""
            lines.append(f"{prefix}[{ctype}] name={name!r} value={value!r}{marker}")

        for child in control.GetChildren():
            walk(child, depth + 1, max_depth, lines, prefix + "  ")
    except Exception as exc:
        lines.append(f"{prefix}(读取失败: {exc})")


def find_window(keyword: str):
    root = auto.GetRootControl()
    for win in root.GetChildren():
        title = win.Name or ""
        if keyword in title and win.ControlTypeName == "WindowControl":
            return win
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="扫描期货软件 UI 树，找价格控件")
    parser.add_argument("--window", default="", help="窗口标题关键字")
    parser.add_argument("--depth", type=int, default=12, help="扫描深度")
    args = parser.parse_args()

    if not args.window:
        print("当前可见顶层窗口：")
        root = auto.GetRootControl()
        for win in root.GetChildren():
            if win.ControlTypeName == "WindowControl" and win.Name:
                print(f"  - {win.Name}")
        print("\n请指定: python discover_ui.py --window \"行情交易系统\"")
        return

    win = find_window(args.window)
    if not win:
        print(f"未找到包含 {args.window!r} 的窗口，请先打开软件")
        sys.exit(1)

    print(f"窗口: {win.Name}")
    print(f"ClassName: {win.ClassName}")
    print("-" * 60)

    lines: list[str] = []
    walk(win, 0, args.depth, lines)
    for line in lines:
        print(line)


if __name__ == "__main__":
    main()
