"""Check whether the inherited console mode gates msvcrt key detection.

``terminal_quit_key_listener`` reads Windows keys through ``msvcrt.kbhit`` and
``msvcrt.getwch`` and never calls ``SetConsoleMode``. This probe allocates its
own private console, injects one ``q`` key event, and measures detection in
canonical line-input mode against a raw control. It never touches the shared
session console.
"""

from __future__ import annotations

import ctypes
import sys
import threading
from ctypes import wintypes

ENABLE_PROCESSED_INPUT = 0x0001
ENABLE_LINE_INPUT = 0x0002
ENABLE_ECHO_INPUT = 0x0004
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
KEY_EVENT = 0x0001
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
WAIT_SECONDS = 5.0
QUIT_KEY = "q"


class _CharUnion(ctypes.Union):
    """The character member of a key event record."""

    _fields_ = [("UnicodeChar", wintypes.WCHAR), ("AsciiChar", wintypes.CHAR)]


class _KeyEventRecord(ctypes.Structure):
    """A Windows key event record."""

    _fields_ = [
        ("bKeyDown", wintypes.BOOL),
        ("wRepeatCount", wintypes.WORD),
        ("wVirtualKeyCode", wintypes.WORD),
        ("wVirtualScanCode", wintypes.WORD),
        ("uChar", _CharUnion),
        ("dwControlKeyState", wintypes.DWORD),
    ]


class _EventUnion(ctypes.Union):
    """The event payload union."""

    _fields_ = [("KeyEvent", _KeyEventRecord)]


class _InputRecord(ctypes.Structure):
    """A Windows console input record."""

    _fields_ = [("EventType", wintypes.WORD), ("Event", _EventUnion)]


def _kernel32() -> ctypes.WinDLL:
    """Load kernel32 with the argument types used by this probe."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.GetConsoleMode.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetConsoleMode.restype = wintypes.BOOL
    kernel32.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.SetConsoleMode.restype = wintypes.BOOL
    kernel32.WriteConsoleInputW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_InputRecord),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.WriteConsoleInputW.restype = wintypes.BOOL
    return kernel32


def _bind_console_stdin(kernel32: ctypes.WinDLL) -> int | None:
    """Rebind CRT file descriptor 0 to this process console input buffer."""
    import msvcrt
    import os

    raw = kernel32.CreateFileW(
        "CONIN$",
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    if not raw or raw == INVALID_HANDLE_VALUE:
        print(f"open_conin=FAILED error={ctypes.get_last_error()}", flush=True)
        return None
    descriptor = msvcrt.open_osfhandle(raw, os.O_RDONLY)
    os.dup2(descriptor, 0)
    os.close(descriptor)
    return msvcrt.get_osfhandle(0)


def _measure(kernel32: ctypes.WinDLL, handle: int, label: str, flags: int) -> bool:
    """Inject one quit key under ``flags`` and report whether it is delivered."""
    import msvcrt

    if not kernel32.SetConsoleMode(handle, flags):
        print(f"{label}: set_mode=FAILED error={ctypes.get_last_error()}", flush=True)
        return False
    actual = wintypes.DWORD()
    kernel32.GetConsoleMode(handle, ctypes.byref(actual))

    record = _InputRecord()
    record.EventType = KEY_EVENT
    record.Event.KeyEvent.bKeyDown = True
    record.Event.KeyEvent.wRepeatCount = 1
    record.Event.KeyEvent.wVirtualKeyCode = ord(QUIT_KEY.upper())
    record.Event.KeyEvent.wVirtualScanCode = 0x10
    record.Event.KeyEvent.uChar.UnicodeChar = QUIT_KEY
    written = wintypes.DWORD()
    injected = kernel32.WriteConsoleInputW(
        handle, ctypes.byref(record), 1, ctypes.byref(written)
    )
    if not injected:
        print(f"{label}: inject=FAILED error={ctypes.get_last_error()}", flush=True)
        return False

    observed: dict[str, object] = {}

    def _read() -> None:
        observed["kbhit"] = msvcrt.kbhit()
        if observed["kbhit"]:
            observed["char"] = msvcrt.getwch()

    worker = threading.Thread(target=_read, name="console-read", daemon=True)
    worker.start()
    worker.join(WAIT_SECONDS)
    if worker.is_alive():
        print(
            f"{label}: mode=0x{actual.value:04x} injected={written.value} "
            f"result=BLOCKED",
            flush=True,
        )
        return False
    print(
        f"{label}: mode=0x{actual.value:04x} injected={written.value} "
        f"kbhit={observed.get('kbhit')} char={observed.get('char')!r}",
        flush=True,
    )
    return True


def _private_console(kernel32: ctypes.WinDLL) -> bool:
    """Attach a console this process owns, detaching any inherited one first."""
    if kernel32.AllocConsole():
        return True
    # An inherited console would make the injection touch another reader's
    # input buffer, so detach and allocate a private one instead.
    kernel32.FreeConsole()
    return bool(kernel32.AllocConsole())


def main() -> int:
    """Measure key detection in canonical line-input mode and in raw mode."""
    if sys.platform != "win32":
        print(f"SKIP: platform={sys.platform}", flush=True)
        return 1
    kernel32 = _kernel32()
    if not _private_console(kernel32):
        print(
            f"SKIP: cannot allocate a private console error={ctypes.get_last_error()}",
            flush=True,
        )
        return 1
    print("private_console=True", flush=True)
    try:
        handle = _bind_console_stdin(kernel32)
        if handle is None:
            return 1
        cooked = ENABLE_PROCESSED_INPUT | ENABLE_LINE_INPUT | ENABLE_ECHO_INPUT
        raw = ENABLE_PROCESSED_INPUT
        if not _measure(kernel32, handle, "canonical_line_input", cooked):
            print("raw_control=SKIPPED after a blocked or failed first run")
            return 0
        _measure(kernel32, handle, "raw_control", raw)
    finally:
        kernel32.FreeConsole()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())