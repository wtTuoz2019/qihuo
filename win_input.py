"""Windows 桌面输入 — 自绘期货软件用屏幕坐标点击最稳。

方案对比（本项目两款软件都是自绘界面，读不到控件）:
  pywinauto / UI Automation  — 控件树空，点不到按钮
  OCR 找按钮               — 慢、易误点，不适合下单
  坐标点击 (SetCursorPos)  — 延迟低、不依赖控件，窗口位置固定即可
"""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes

if sys.platform != "win32":
    raise RuntimeError("win_input 仅支持 Windows")

user32 = ctypes.windll.user32
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
SW_RESTORE = 9


def click_xy(x: int, y: int, pause: float = 0.04) -> None:
    user32.SetCursorPos(int(x), int(y))
    time.sleep(pause)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.03)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def foreground_by_title(keyword: str) -> bool:
    found = ctypes.c_void_p()

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def _enum(hwnd, _lp):
        if not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        if keyword and keyword in buf.value:
            found.value = hwnd
            return False
        return True

    user32.EnumWindows(_enum, 0)
    if not found.value:
        return False
    user32.ShowWindow(found.value, SW_RESTORE)
    user32.SetForegroundWindow(found.value)
    time.sleep(0.08)
    return True
