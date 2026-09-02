"""OCR 引擎 — Windows 默认用系统自带 OCR（安装快，无需 PyTorch）。"""

from __future__ import annotations

import sys
from io import BytesIO
from typing import Optional

import numpy as np
from PIL import Image

_ENGINE = "auto"
_TESSERACT_CMD = ""
_EASYOCR_READER = None
_LAST_ENGINE_USED = ""

TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
]


def configure(engine: str = "auto", tesseract_cmd: str = "") -> None:
    global _ENGINE, _TESSERACT_CMD
    _ENGINE = (engine or "auto").lower()
    _TESSERACT_CMD = tesseract_cmd or ""


def last_engine_used() -> str:
    return _LAST_ENGINE_USED


def _set_used(name: str) -> str:
    global _LAST_ENGINE_USED
    _LAST_ENGINE_USED = name
    return name


def _find_tesseract() -> Optional[str]:
    if _TESSERACT_CMD:
        from pathlib import Path

        if Path(_TESSERACT_CMD).exists():
            return _TESSERACT_CMD
    from pathlib import Path

    for p in TESSERACT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _ocr_easyocr(img: Image.Image) -> str:
    global _EASYOCR_READER
    import easyocr

    if _EASYOCR_READER is None:
        print("  [OCR] 首次加载 EasyOCR 模型，约需 30 秒…")
        _EASYOCR_READER = easyocr.Reader(["en"], gpu=False, verbose=False)

    arr = np.array(img)
    results = _EASYOCR_READER.readtext(
        arr,
        allowlist="0123456789.",
        paragraph=False,
        detail=1,
    )
    return " ".join(str(item[1]) for item in results)


def _ocr_tesseract(img: Image.Image) -> str:
    import pytesseract

    cmd = _find_tesseract()
    if not cmd:
        raise RuntimeError("未找到 Tesseract，可在 config.yaml 设置 ocr.tesseract_cmd")
    pytesseract.pytesseract.tesseract_cmd = cmd
    config = r"--psm 7 -c tessedit_char_whitelist=0123456789."
    return pytesseract.image_to_string(img, config=config)


def _ocr_windows(img: Image.Image) -> str:
    """Windows 10/11 自带 OCR，无需额外安装。"""
    import asyncio

    async def _run() -> str:
        from winrt.windows.graphics.imaging import BitmapDecoder
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

        buf = BytesIO()
        img.save(buf, format="PNG")
        data = buf.getvalue()

        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(data)
        await writer.store_async()
        await writer.flush_async()
        stream.seek(0)

        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()

        engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            from winrt.windows.globalization import Language

            engine = OcrEngine.try_create_from_language(Language("en"))
        if engine is None:
            raise RuntimeError("Windows OCR 不可用")

        result = await engine.recognize_async(bitmap)
        return result.text or ""

    return asyncio.run(_run())


def _try_engine(name: str, img: Image.Image) -> Optional[str]:
    try:
        if name == "easyocr":
            return _ocr_easyocr(img)
        if name == "tesseract":
            return _ocr_tesseract(img)
        if name == "windows":
            return _ocr_windows(img)
    except Exception:
        return None
    return None


def _engine_order() -> list[str]:
    if _ENGINE == "auto":
        if sys.platform == "win32":
            return ["windows", "tesseract", "easyocr"]
        return ["easyocr", "tesseract"]
    return [_ENGINE]


def ocr_image(img: Image.Image) -> str:
    errors: list[str] = []
    for name in _engine_order():
        try:
            if name == "easyocr":
                text = _ocr_easyocr(img)
                return _set_used("easyocr") and text
            if name == "windows":
                text = _ocr_windows(img)
                return _set_used("windows") and text
            if name == "tesseract":
                text = _ocr_tesseract(img)
                return _set_used("tesseract") and text
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    raise RuntimeError(
        "所有 OCR 引擎均不可用。\n"
        "Windows 推荐（安装快）:\n"
        "  python -m pip install winrt-runtime winrt-Windows.Media.Ocr "
        "winrt-Windows.Graphics.Imaging winrt-Windows.Storage.Streams winrt-Windows.Globalization\n"
        "并在 config.yaml 设置 ocr.engine: windows\n"
        + "\n".join(errors)
    )


def check_engines() -> dict[str, str]:
    """返回各引擎状态，供 check_env 使用。"""
    status: dict[str, str] = {}
    winrt_cmd = (
        "python -m pip install winrt-runtime winrt-Windows.Media.Ocr "
        "winrt-Windows.Graphics.Imaging winrt-Windows.Storage.Streams winrt-Windows.Globalization"
    )

    if sys.platform == "win32":
        try:
            import winrt  # noqa: F401

            status["windows"] = "ok ← 推荐，Win10/11 内置 OCR，安装快"
        except ImportError:
            status["windows"] = f"缺失 → {winrt_cmd}"
    else:
        status["windows"] = "仅 Windows"

    try:
        import easyocr  # noqa: F401

        status["easyocr"] = "ok（备选，体积大、安装慢，含 PyTorch）"
    except ImportError:
        status["easyocr"] = "未装（可不装，用 windows 即可）"

    cmd = _find_tesseract()
    if cmd:
        status["tesseract"] = f"ok ({cmd})"
    else:
        status["tesseract"] = "未安装（可选）"

    return status
