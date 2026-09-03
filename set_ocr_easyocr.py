"""一键在 config.yaml 写入 ocr.engine: easyocr（Windows 上运行一次即可）。"""

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
        print("找不到 config.yaml，请先: copy config.example.yaml config.yaml")
        raise SystemExit(1)

    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    cfg["ocr"] = {"engine": "easyocr", "tesseract_cmd": ""}
    CONFIG.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print("✓ 已写入 config.yaml:")
    print("  ocr:")
    print("    engine: easyocr")
    print("    tesseract_cmd: ''")


if __name__ == "__main__":
    main()
