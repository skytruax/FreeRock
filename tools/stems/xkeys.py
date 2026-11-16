"""Presses keys on a screen nobody sees, for answering a program's first-run questions.

    uv run --with python-xlib python tools/stems/xkeys.py :97 Tab Return

Each argument after the display is the name of a key (an X keysym: Return, Tab, space, n, Escape).
"""
import sys
import time

from Xlib import XK, X, display
from Xlib.ext import xtest

screen = display.Display(sys.argv[1])
for name in sys.argv[2:]:
    keysym = XK.string_to_keysym(name)
    if keysym == 0:
        raise SystemExit("no key called %r" % name)
    code = screen.keysym_to_keycode(keysym)
    xtest.fake_input(screen, X.KeyPress, code)
    xtest.fake_input(screen, X.KeyRelease, code)
    screen.sync()
    time.sleep(0.25)
screen.close()
