# -*- coding: utf-8 -*-
"""Smoke test: khởi tạo toàn bộ stack và chạy thử các bộ nhận diện (không gửi phím)."""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
cfg = json.load(open(cfg_path, encoding="utf-8"))

from vision import Vision
from controller import InputController
from fight import FightController

v = Vision(cfg)
i = InputController(cfg)
f = FightController(cfg, v, i)
g, m, w = v.fight_bar()
print(f"SMOKE OK - {v.W}x{v.H} | fight_bar w={w} green={g} marker={m}")
print(f"detectors: idle={v.is_idle()} bite={v.is_bite()} fight={v.is_fighting()} result={v.is_result()}")
print(f"foreground='{i.foreground_title()}'")
