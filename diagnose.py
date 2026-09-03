"""诊断：窗口是否找到、UI/区域读价是否正常。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("pip install pyyaml")
    sys.exit(1)

from quote_reader import QuoteLabels, RegionSet, SoftwareConfig, list_windows, read_quote


def load_sw(raw: dict) -> SoftwareConfig:
    lb = raw.get("labels") or {}
    return SoftwareConfig(
        window_title=raw.get("window_title", ""),
        read_mode=raw.get("read_mode", "auto"),
        labels=QuoteLabels(
            bid=lb.get("bid", "买入"),
            ask=lb.get("ask", "卖出"),
            last=lb.get("last", ""),
        ),
        bid_control_name=raw.get("bid_control_name") or "",
        ask_control_name=raw.get("ask_control_name") or "",
        last_control_name=raw.get("last_control_name") or "",
        regions=RegionSet.from_dict(raw.get("regions")),
    )


def _overlap(a, b) -> bool:
    if not a or not b:
        return False
    ax2, ay2 = a.x + a.w, a.y + a.h
    bx2, by2 = b.x + b.w, b.y + b.h
    return not (ax2 < b.x or bx2 < a.x or ay2 < b.y or by2 < a.y)


def test_one(name: str, cfg: SoftwareConfig, lo: float, hi: float) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {name}  window_title={cfg.window_title!r}  mode={cfg.read_mode}")
    print(f"  regions={cfg.regions}")
    if _overlap(cfg.regions.bid, cfg.regions.ask):
        print("  ⚠ bid 和 ask 区域重叠，请分别框「买价」和「卖价」，不要框同一个数字")
    q, st = read_quote(cfg, lo, hi)
    print(f"  窗口找到: {st.window_found}  标题: {st.window_title!r}")
    print(f"  读取模式: {st.mode_used}  控件数: {st.control_count}")
    if st.error:
        print(f"  错误: {st.error}")
    print(f"  结果: bid={q.bid} ask={q.ask} last={q.last} valid={q.valid()}")

    from paths import log_path
    from region_reader import ocr_region

    for field in ("bid", "ask", "last"):
        region = getattr(cfg.regions, field)
        if not region:
            continue
        try:
            shot = log_path(f"debug_{name}_{field}.png")
            price, raw = ocr_region(
                region, lo, hi, save_debug=str(shot), return_text=True
            )
            print(f"  {field}: {price}  OCR原文={raw!r}  截图={shot}")
        except Exception as exc:
            print(f"  {field} 调试失败: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    path = Path(args.config)
    if not path.exists():
        print(f"找不到 {path}")
        sys.exit(1)

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    lo, hi = raw.get("price_range", [10000, 99999])

    from region_reader import init_ocr_from_config

    init_ocr_from_config(raw.get("ocr"))

    print("当前可见窗口:")
    for t in list_windows():
        print(f"  - {t}")

    test_one("software_a", load_sw(raw["software_a"]), lo, hi)
    test_one("software_b", load_sw(raw["software_b"]), lo, hi)

    print("\n" + "=" * 60)
    print("打开 logs/debug_*.png 看框选是否盖住价格数字。")
    print("若 OCR原文 为空或不是价格，重新标定该字段。")


if __name__ == "__main__":
    main()
