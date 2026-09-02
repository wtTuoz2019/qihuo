"""安装后快速检查：Python 依赖 + OCR 引擎。"""

from __future__ import annotations

import sys

from ocr_engine import check_engines, configure, ocr_image
from PIL import Image, ImageDraw, ImageFont


def _test_ocr() -> None:
    img = Image.new("L", (120, 32), color=0)
    draw = ImageDraw.Draw(img)
    draw.text((8, 6), "29509.75", fill=255)
    text = ocr_image(img)
    if "29509" in text.replace(" ", ""):
        print("  ✓ OCR 实测通过")
    else:
        print(f"  △ OCR 实测结果: {text!r}（若读价正常可忽略）")


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
    print("OCR 引擎（无需 Tesseract，推荐 EasyOCR）:")
    configure(engine="easyocr")
    for name, msg in check_engines().items():
        print(f"  [{name}] {msg}")

    print()
    try:
        _test_ocr()
    except Exception as exc:
        print(f"  ✗ OCR 测试失败: {exc}")
        print("    请运行: python -m pip install easyocr")
        print("    首次会下载约 100MB 模型，需联网")

    print()
    print("下一步:")
    print("  python calibrate_regions.py --target software_a")
    print("  python calibrate_regions.py --target software_b")
    print("  python diagnose.py")


if __name__ == "__main__":
    main()
