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

PRICE_FROM_TEXT = re.compile(r"(\d{4,6}(?:\.\d{1,2})?)")


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


def _upscale(img: Image.Image, scale: int = 3) -> Image.Image:
    return img.resize(
        (max(img.width * scale, 80), max(img.height * scale, 28)),
        Image.Resampling.LANCZOS,
    )


def _preprocess(img: Image.Image) -> Image.Image:
    gray = img.convert("L")
    up = _upscale(gray)
    arr = np.array(up)
    boosted = np.clip((arr.astype(np.float32) - 50) * 2.5, 0, 255).astype(np.uint8)
    return ImageOps.autocontrast(Image.fromarray(boosted))


def _parse_price_text(text: str, lo: float, hi: float) -> Optional[float]:
    cleaned = (
        text.replace(",", "")
        .replace(" ", "")
        .replace("O", "0")
        .replace("o", "0")
        .replace("l", "1")
        .replace("I", "1")
    )
    for m in PRICE_FROM_TEXT.findall(cleaned):
        val = float(m)
        if lo <= val <= hi:
            return val
    digits = re.sub(r"[^\d.]", "", cleaned)
    if not digits:
        return None
    try:
        if digits.count(".") == 1:
            val = float(digits)
        elif digits.isdigit() and 6 <= len(digits) <= 8:
            # 2917675 → 29176.75 （纳指常见两位小数）
            val = float(digits[:-2] + "." + digits[-2:])
        elif digits.isdigit():
            val = float(digits)
        else:
            return None
        if lo <= val <= hi:
            return val
    except ValueError:
        pass
    return None


def ocr_region(
    region: Region,
    lo: float,
    hi: float,
    save_debug: str = "",
    return_text: bool = False,
):
    img = _capture(region)
    color = _upscale(img)
    gray = _preprocess(img)
    if save_debug:
        color.save(save_debug)
        gray.save(save_debug.replace(".png", "_gray.png"))

    texts: list[str] = []
    price = None
    for candidate in (color, gray):
        text = ocr_image(candidate)
        texts.append(text)
        price = _parse_price_text(text, lo, hi)
        if price is not None:
            break
    raw = " | ".join(t for t in texts if t)
    if return_text:
        return price, raw
    return price


def read_regions(regions: RegionSet, lo: float, hi: float) -> tuple[Optional[float], Optional[float], Optional[float]]:
    bid = ocr_region(regions.bid, lo, hi) if regions.bid else None
    ask = ocr_region(regions.ask, lo, hi) if regions.ask else None
    last = ocr_region(regions.last, lo, hi) if regions.last else None
    return bid, ask, last
