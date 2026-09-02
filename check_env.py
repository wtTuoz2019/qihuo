"""安装后快速检查：Python 依赖 + Tesseract OCR。"""

from __future__ import annotations

import sys


def main() -> None:
    print("=" * 50)
    print("  环境检查")
    print("=" * 50)
    print(f"Python: {sys.version}")

    mods = ["yaml", "uiautomation", "mss", "PIL", "numpy", "pytesseract"]
    for m in mods:
        try:
            __import__(m)
            print(f"  ✓ {m}")
        except ImportError:
            print(f"  ✗ {m}  缺失 → python -m pip install -r requirements.txt")

    print()
    try:
        from region_reader import _setup_tesseract
        import pytesseract

        _setup_tesseract()
        ver = pytesseract.get_tesseract_version()
        print(f"  ✓ Tesseract {ver}")
    except Exception as exc:
        print(f"  ✗ Tesseract 不可用: {exc}")
        print("    安装: https://github.com/UB-Mannheim/tesseract/wiki")
        print("    安装时勾选 Add to PATH")

    print()
    print("全部 ✓ 后运行:")
    print("  python calibrate_regions.py --target software_a")
    print("  python calibrate_regions.py --target software_b")
    print("  python diagnose.py")


if __name__ == "__main__":
    main()
