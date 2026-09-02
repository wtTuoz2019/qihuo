"""屏幕固定区域读价 — 期货客户端自绘界面时用这个。"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import mss
    import numpy as np
    from PIL import Image, ImageOps
except ImportError:
    mss = None
    np = None
    Image = None
    ImageOps = None

PRICE_FROM_TEXT = re.compile(r"(\d{1,6}\.\d{1,2})")

# Windows 常见 Tesseract 安装路径
_TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


@dataclass
class Region:
    x: int
    y: int
    w: int
    h: int

    @classmethod
    def from_list(cls, arr: list) -> "Region":
        if len(arr) != 4:
            raise ValueError(f"region 需要 [x,y,w,h]，当前: {arr}")
        return cls(int(arr[0]), int(arr[1]), int(arr[2]), int(arr[3]))

    def valid(self) -> bool:
        return self.w > 0 and self.h > 0


@dataclass
class RegionSet:
    bid: Optional[Region] = None
    ask: Optional[Region] = None
    last: Optional[Region] = None

    @classmethod
    def from_dict(cls, d: dict | None) -> "RegionSet":
        if not d:
            return cls()
        out = cls()
        for key in ("bid", "ask", "last"):
            raw = d.get(key)
            if raw and len(raw) == 4 and raw[2] > 0 and raw[3] > 0:
                setattr(out, key, Region.from_list(raw))
        return out

    def any(self) -> bool:
        return any((self.bid, self.ask, self.last))


def _setup_tesseract() -> None:
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError(
            "请安装 OCR 依赖:\n"
            "  python -m pip install mss pillow numpy pytesseract\n"
            "并安装 Tesseract:\n"
            "  https://github.com/UB-Mannheim/tesseract/wiki"
        ) from exc

    for p in _TESSERACT_CANDIDATES:
        if Path(p).exists():
            pytesseract.pytesseract.tesseract_cmd = p
            return


def _capture(region: Region) -> Image.Image:
    if mss is None:
        raise RuntimeError("缺少 mss / pillow: python -m pip install mss pillow numpy")
    with mss.mss() as sct:
        shot = sct.grab({"left": region.x, "top": region.y, "width": region.w, "height": region.h})
        return Image.frombytes("RGB", shot.size, shot.bgr, "raw", "BGRX")


def _preprocess(img: Image.Image) -> Image.Image:
    # 放大 + 提对比，专用于绿色/白色数字
    gray = img.convert("L")
    up = gray.resize((max(gray.width * 3, 60), max(gray.height * 3, 24)), Image.Resampling.LANCZOS)
    arr = np.array(up)
    boosted = np.clip((arr.astype(np.float32) - 50) * 2.5, 0, 255).astype(np.uint8)
    binary = Image.fromarray(boosted)
    return ImageOps.autocontrast(binary)


def _parse_price_text(text: str, lo: float, hi: float) -> Optional[float]:
    cleaned = text.replace(",", "").replace(" ", "")
    for m in PRICE_FROM_TEXT.findall(cleaned):
        val = float(m)
        if lo <= val <= hi:
            return val
    digits = re.sub(r"[^\d.]", "", cleaned)
    if digits.count(".") == 1:
        try:
            val = float(digits)
            if lo <= val <= hi:
                return val
        except ValueError:
            pass
    return None


def _ocr_tesseract(img: Image.Image) -> str:
    import pytesseract

    _setup_tesseract()
    config = r"--psm 7 -c tessedit_char_whitelist=0123456789."
    return pytesseract.image_to_string(img, config=config)


def _ocr_rapidocr(img: Image.Image) -> str:
    from rapidocr_onnxruntime import RapidOCR

    ocr = RapidOCR()
    result, _ = ocr(np.array(img))
    if not result:
        return ""
    return " ".join(item[1] for item in result)


def _ocr_text(img: Image.Image) -> str:
    # Python 3.12+ 优先 tesseract；3.11 及以下可试 rapidocr
    if sys.version_info >= (3, 12):
        return _ocr_tesseract(img)
    try:
        return _ocr_rapidocr(img)
    except ImportError:
        return _ocr_tesseract(img)


def ocr_region(region: Region, lo: float, hi: float, save_debug: str = "") -> Optional[float]:
    img = _capture(region)
    proc = _preprocess(img)
    if save_debug:
        proc.save(save_debug)

    text = _ocr_text(proc)
    return _parse_price_text(text, lo, hi)


def read_regions(regions: RegionSet, lo: float, hi: float) -> tuple[Optional[float], Optional[float], Optional[float]]:
    bid = ocr_region(regions.bid, lo, hi) if regions.bid else None
    ask = ocr_region(regions.ask, lo, hi) if regions.ask else None
    last = ocr_region(regions.last, lo, hi) if regions.last else None
    return bid, ask, last
