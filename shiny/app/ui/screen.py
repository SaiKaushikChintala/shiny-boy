import ctypes
import os
import sys
from ctypes import wintypes

MONITOR_DEFAULTTONEAREST = 2


class _MonitorInfo(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT), ("work", wintypes.RECT), ("flags", wintypes.DWORD)]


def work_area(x: int, y: int, fallback: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    if sys.platform != "win32":
        return fallback
    try:
        user32 = ctypes.windll.user32
        user32.MonitorFromPoint.restype = wintypes.HANDLE
        user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MonitorInfo)]
        handle = user32.MonitorFromPoint(wintypes.POINT(int(x), int(y)), MONITOR_DEFAULTTONEAREST)
        info = _MonitorInfo()
        info.size = ctypes.sizeof(_MonitorInfo)
        if handle and user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            return info.work.left, info.work.top, info.work.right, info.work.bottom
    except (OSError, AttributeError):
        pass
    return fallback


def place_in_monitor(x: int, y: int, width: int, height: int, anchor_x: int | None = None, anchor_y: int | None = None) -> tuple[int, int]:
    left, top, right, bottom = work_area(anchor_x if anchor_x is not None else x, anchor_y if anchor_y is not None else y, (0, 0, 10**6, 10**6))
    return max(left, min(x, right - width)), max(top, min(y, bottom - height))


def app_in_foreground() -> bool:
    if sys.platform != "win32":
        return True
    try:
        user32 = ctypes.windll.user32
        handle = user32.GetForegroundWindow()
        if not handle:
            return False
        process = wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(process))
        return process.value == os.getpid()
    except (OSError, AttributeError):
        return True
