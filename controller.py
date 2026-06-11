# -*- coding: utf-8 -*-
"""Gửi phím/chuột vào game qua SendInput scancode (pydirectinput) + kiểm tra cửa sổ game."""
import ctypes
import random
import time

import pydirectinput

pydirectinput.PAUSE = 0
pydirectinput.FAILSAFE = False


class InputController:
    def __init__(self, cfg):
        self.cfg = cfg
        keys = cfg["keys"]
        self._safety_keys = {keys["pull_left"], keys["pull_right"], keys["cast"]}
        self.held = None
        self.titles = [t.lower() for t in cfg.get("window_titles", [])]
        self.require_fg = bool(cfg.get("require_game_foreground", True))

    def foreground_title(self):
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
        return buf.value

    def game_focused(self):
        """Chỉ bơm phím khi cửa sổ game đang focus (SendInput đi vào cửa sổ foreground)."""
        if not self.require_fg or not self.titles:
            return True
        title = self.foreground_title().lower()
        return any(s in title for s in self.titles)

    def tap(self, key, dur=0.08, jitter=0.025):
        """Nhấn-giữ-nhả một phím; UE5 đọc input theo frame nên cần giữ vài chục ms."""
        pydirectinput.keyDown(key)
        time.sleep(dur + random.uniform(0.0, jitter))
        pydirectinput.keyUp(key)

    def hold(self, key):
        if self.held == key:
            return
        self.release()
        pydirectinput.keyDown(key)
        self.held = key

    def release(self):
        if self.held is not None:
            pydirectinput.keyUp(self.held)
            self.held = None

    def release_all(self):
        """Nhả mọi phím có thể đang giữ — gọi khi tạm dừng/thoát/mất focus."""
        for k in self._safety_keys:
            pydirectinput.keyUp(k)
        self.held = None

    def click_at(self, fx, fy, vision):
        """Click chuột trái tại tọa độ tỉ lệ (fx, fy) của màn hình chính."""
        x = vision.mon_left + int(fx * vision.W)
        y = vision.mon_top + int(fy * vision.H)
        pydirectinput.moveTo(x, y)
        time.sleep(0.06 + random.uniform(0.0, 0.04))
        pydirectinput.click()
