"""Native window material on macOS: real glass behind the window.

Through the Objective-C runtime (ctypes, no extra dependency) the window gets
a full-size content view under a transparent title bar, a dark appearance and
an NSVisualEffectView behind Qt's view, so the desktop shows through, blurred,
as in Finder's sidebar. Anywhere else, or if anything fails, the app keeps its
painted black background.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import platform
import sys

_NS_FULL_SIZE_CONTENT_VIEW = 1 << 15
_NS_TITLE_HIDDEN = 1
_NS_WINDOW_BELOW = -1
_MATERIAL_UNDER_WINDOW_BACKGROUND = 21
_BLENDING_BEHIND_WINDOW = 0
_STATE_ACTIVE = 1
_AUTORESIZE_WIDTH_HEIGHT = 2 | 16

# Height of the title bar area the content now extends under, and room for
# the traffic-light buttons on the left.
TITLEBAR_HEIGHT = 28
TRAFFIC_LIGHTS_WIDTH = 72


class _NSRect(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double),
                ("w", ctypes.c_double), ("h", ctypes.c_double)]  # fmt: skip


class _ObjC:
    def __init__(self) -> None:
        self.lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
        self.lib.objc_getClass.restype = ctypes.c_void_p
        self.lib.objc_getClass.argtypes = [ctypes.c_char_p]
        self.lib.sel_registerName.restype = ctypes.c_void_p
        self.lib.sel_registerName.argtypes = [ctypes.c_char_p]
        self.send_addr = ctypes.cast(self.lib.objc_msgSend, ctypes.c_void_p).value

    def cls(self, name: str) -> int:
        return self.lib.objc_getClass(name.encode())

    def send(self, obj, sel: str, *args, restype=ctypes.c_void_p, argtypes=()):
        fn = ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p, *argtypes)(self.send_addr)
        return fn(obj, self.lib.sel_registerName(sel.encode()), *args)

    def nsstring(self, text: str) -> int:
        return self.send(self.cls("NSString"), "stringWithUTF8String:", text.encode(),
                         argtypes=(ctypes.c_char_p,))  # fmt: skip


def apply_macos_glass(widget) -> bool:
    """Call after the window is shown. Returns True if the native glass is on."""
    if sys.platform != "darwin" or platform.machine() != "arm64":
        # Intel Macs would need objc_msgSend_stret for NSRect returns; not supported.
        return False
    try:
        rt = _ObjC()
        view = ctypes.c_void_p(int(widget.winId()))
        window = rt.send(view, "window")
        superview = rt.send(view, "superview")
        if not window or not superview:
            return False
        mask = rt.send(window, "styleMask", restype=ctypes.c_ulong)
        rt.send(window, "setStyleMask:", mask | _NS_FULL_SIZE_CONTENT_VIEW,
                argtypes=(ctypes.c_ulong,))  # fmt: skip
        rt.send(window, "setTitlebarAppearsTransparent:", True, argtypes=(ctypes.c_bool,))
        rt.send(window, "setTitleVisibility:", _NS_TITLE_HIDDEN, argtypes=(ctypes.c_long,))
        name = rt.nsstring("NSAppearanceNameDarkAqua")
        dark = rt.send(rt.cls("NSAppearance"), "appearanceNamed:", name,
                       argtypes=(ctypes.c_void_p,))  # fmt: skip
        if dark:
            rt.send(window, "setAppearance:", dark, argtypes=(ctypes.c_void_p,))

        bounds = rt.send(superview, "bounds", restype=_NSRect)
        effect = rt.send(rt.cls("NSVisualEffectView"), "alloc")
        effect = rt.send(effect, "initWithFrame:", bounds, argtypes=(_NSRect,))
        for sel, value in (
            ("setMaterial:", _MATERIAL_UNDER_WINDOW_BACKGROUND),
            ("setBlendingMode:", _BLENDING_BEHIND_WINDOW),
            ("setState:", _STATE_ACTIVE),
        ):
            rt.send(effect, sel, value, argtypes=(ctypes.c_long,))
        rt.send(effect, "setAutoresizingMask:", _AUTORESIZE_WIDTH_HEIGHT,
                argtypes=(ctypes.c_ulong,))  # fmt: skip
        rt.send(superview, "addSubview:positioned:relativeTo:", effect, _NS_WINDOW_BELOW, view,
                argtypes=(ctypes.c_void_p, ctypes.c_long, ctypes.c_void_p))  # fmt: skip
        return True
    except (OSError, AttributeError, TypeError, ValueError):
        return False
