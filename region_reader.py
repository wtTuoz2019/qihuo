"""屏幕固定区域读价 — 期货客户端自绘界面时用这个。"""

from __future__ import annotations

import re
from dataclasses import dataclass
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

from ocr_engine import configure, ocr_image

PRICE_FROM_TEXT = re.compile(r"(\d{1,6}\.\d{1,2})")


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


def init_ocr_from_config(ocr_cfg: dict | None) -> None:
    ocr_cfg = ocr_cfg or {}
    configure(
        engine=ocr_cfg.get("engine", "easyocr"),
        tesseract_cmd=ocr_cfg.get("tesseract_cmd", ""),
    )


def _capture(region: Region) -> Image.Image:
    if mss is None:
        raise RuntimeError("缺少 mss / pillow: python -m pip install mss pillow numpy")
    with mss.mss() as sct:
        shot = sct.grab({"left": region.x, "top": region.y, "width": region.w, "height": region.h})
        if hasattr(shot, "rgb"):
            return Image.frombytes("RGB", shot.size, shot.rgb)
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def _preprocess(img: Image.Image) -> Image.Image:
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


def ocr_region(region: Region, lo: float, hi: float, save_debug: str = "") -> Optional[float]:
    img = _capture(region)
    proc = _preprocess(img)
    if save_debug:
        proc.save(save_debug)

    text = ocr_image(proc)
    return _parse_price_text(text, lo, hi)


def read_regions(regions: RegionSet, lo: float, hi: float) -> tuple[Optional[float], Optional[float], Optional[float]]:
    bid = ocr_region(regions.bid, lo, hi) if regions.bid else None
    ask = ocr_region(regions.ask, lo, hi) if regions.ask else None
    last = ocr_region(regions.last, lo, hi) if regions.last else None
    return bid, ask, last
