"""
标定屏幕价格区域 — 在 Windows 上运行。

用法:
  python calibrate_regions.py
  python calibrate_regions.py --target software_a
  python calibrate_regions.py --target software_b --config config.yaml
"""

from __future__ import annotations

import argparse
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


def pick_region(label: str) -> list[int]:
    print(f"\n=== 标定 [{label}] ===")
    input("  1/2 鼠标移到价格左上角，按 Enter...")
    x1, y1 = cursor_pos()
    print(f"      左上: ({x1}, {y1})")
    input("  2/2 鼠标移到价格右下角，按 Enter...")
    x2, y2 = cursor_pos()
    print(f"      右下: ({x2}, {y2})")
    region = [min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)]
    print(f"      区域: {region}")
    ok = input("  确认? [Y/n]: ").strip().lower()
    if ok in ("", "y", "yes"):
        return region
    return pick_region(label)


def main() -> None:
    if sys.platform != "win32":
        print("请在 Windows 上运行")
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--target", choices=["software_a", "software_b"], required=True)
    args = parser.parse_args()

    path = Path(args.config)
    if not path.exists():
        print(f"找不到 {path}，请先 copy config.example.yaml config.yaml")
        sys.exit(1)

    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    block = cfg.setdefault(args.target, {})
    block["read_mode"] = "region"

    print("标定前请：两个软件都打开、价格数字清晰可见、窗口不要遮挡")
    regions: dict[str, list[int]] = {}
    for field in ("bid", "ask", "last"):
        use = input(f"是否标定 {field}? [Y/n]: ").strip().lower()
        if use in ("", "y", "yes"):
            regions[field] = pick_region(field)

    block["regions"] = regions
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"\n已写入 {path} -> {args.target}.regions")
    print("测试: python diagnose.py")


if __name__ == "__main__":
    main()
