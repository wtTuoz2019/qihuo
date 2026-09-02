"""安装后快速检查：Python 依赖 + OCR 引擎。"""

from __future__ import annotations

import sys

from ocr_engine import check_engines, configure, ocr_image
from PIL import Image, ImageDraw


def _test_ocr() -> None:
    img = Image.new("L", (120, 32), color=0)
    draw = ImageDraw.Draw(img)
    draw.text((8, 6), "29509.75", fill=255)
    text = ocr_image(img)
    if "29509" in text.replace(" ", ""):
        print("  ✓ OCR 实测通过")
    else:
        print(f"  △ OCR 实测结果: {text!r}（若 diagnose 读价正常可忽略）")


def main() -> None:
    print("=" * 50)
    print("  环境检查")
    print("=" * 50)
    print(f"Python: {sys.version.split()[0]}")

    mods = ["yaml", "uiautomation", "mss", "PIL", "numpy"]
    for m in mods:
        try:
            __import__(m)
            print(f"  ✓ {m}")
        except ImportError:
            print(f"  ✗ {m}  → python -m pip install -r requirements.txt")

    print()
    print("OCR 引擎（推荐 Windows 内置，安装快，不用 EasyOCR）:")
    configure(engine="windows")
    for name, msg in check_engines().items():
        print(f"  [{name}] {msg}")

    print()
    try:
        _test_ocr()
    except Exception as exc:
        print(f"  ✗ OCR 测试失败: {exc}")
        print("    运行下面这一条（约 1 分钟，比 easyocr 快很多）:")
        print("    python -m pip install winrt-runtime winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging winrt-Windows.Storage.Streams winrt-Windows.Globalization")

    print()
    print("下一步:")
    print("  python diagnose.py")
    print("  python spread_monitor.py")


if __name__ == "__main__":
    main()
