"""Terminal color helpers. Falls back to no-op if not a TTY."""

import sys

_COLOR = sys.stdout.isatty()


def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if _COLOR else str(text)


def red(text):     return _c("31", text)
def green(text):   return _c("32", text)
def yellow(text):  return _c("33", text)
def blue(text):    return _c("34", text)
def cyan(text):    return _c("36", text)
def bold(text):    return _c("1", text)
def dim(text):     return _c("2", text)


def battery_color(percentage, level=""):
    """Color battery percentage based on level."""
    if level == "CRITICAL" or (isinstance(percentage, int) and percentage <= 10):
        return red(f"{percentage}%")
    if level == "LOW" or (isinstance(percentage, int) and percentage <= 25):
        return yellow(f"{percentage}%")
    return green(f"{percentage}%")


def state_color(state):
    """Color device state."""
    if state == "ACTIVE":
        return green(state)
    if state in ("ABSENT", "NOT_CONNECTED", "INACTIVE"):
        return red(state)
    return yellow(state)
