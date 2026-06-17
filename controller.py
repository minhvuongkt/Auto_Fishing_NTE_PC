# -*- coding: utf-8 -*-
"""Gửi phím/chuột vào game qua SendInput scancode (pydirectinput) + kiểm tra cửa sổ game."""
import ctypes
import random
import time

import pydirectinput

pydirectinput.PAUSE = 0
pydirectinput.FAILSAFE = False


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def _cursor_pos():
    pt = _POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


class InputController:
    def __init__(self, cfg, human=None):
        self.cfg = cfg
        self.human = human
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
        hold = self.human.hold(dur) if self.human else dur + random.uniform(0.0, jitter)
        pydirectinput.keyDown(key)
        time.sleep(hold)
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
        """Click chuột trái tại tọa độ tỉ lệ (fx, fy); di chuột theo đường cong + lệch điểm."""
        ox, oy = self.human.click_offset(vision.sx) if self.human else (0, 0)
        x = vision.mon_left + int(fx * vision.W) + ox
        y = vision.mon_top + int(fy * vision.H) + oy
        if self.human:
            cx, cy = _cursor_pos()
            for px, py, dt in self.human.mouse_path(cx, cy, x, y):
                pydirectinput.moveTo(px, py)
                if dt:
                    time.sleep(dt)
            time.sleep(0.03 + random.uniform(0.0, 0.05))
            pydirectinput.mouseDown()
            time.sleep(self.human.click_hold())
            pydirectinput.mouseUp()
        else:
            pydirectinput.moveTo(x, y)
            time.sleep(0.06 + random.uniform(0.0, 0.04))
            pydirectinput.click()

    def move_to(self, fx, fy, vision):
        """Di chuột tới tọa độ tỉ lệ mà không click; dùng để bỏ hover khỏi ROI."""
        x = vision.mon_left + int(fx * vision.W)
        y = vision.mon_top + int(fy * vision.H)
        pydirectinput.moveTo(x, y)
        time.sleep(0.05 + random.uniform(0.0, 0.04))

    def drag(self, fx0, fy0, fx1, fy1, vision, steps=20, hold=0.12, step_delay=0.02):
        """Kéo-thả chuột trái từ (fx0,fy0) tới (fx1,fy1) theo tỉ lệ màn hình.

        Dùng để vuốt ngang cuộn dải ô mồi: nhấn giữ ở điểm đầu, di nhiều bước
        nhỏ tới điểm cuối rồi nhả — game cần thấy chuyển động liên tục mới cuộn.
        """
        x0 = vision.mon_left + int(fx0 * vision.W)
        y0 = vision.mon_top + int(fy0 * vision.H)
        x1 = vision.mon_left + int(fx1 * vision.W)
        y1 = vision.mon_top + int(fy1 * vision.H)
        pydirectinput.moveTo(x0, y0)
        time.sleep(0.05 + random.uniform(0.0, 0.05))
        pydirectinput.mouseDown()
        time.sleep(hold + random.uniform(0.0, 0.05))
        steps = max(2, steps)
        for k in range(1, steps + 1):
            tt = k / steps
            px = int(x0 + (x1 - x0) * tt)
            py = int(y0 + (y1 - y0) * tt)
            pydirectinput.moveTo(px, py)
            time.sleep(step_delay + random.uniform(0.0, step_delay * 0.6))
        time.sleep(0.06 + random.uniform(0.0, 0.06))
        pydirectinput.mouseUp()
        time.sleep(0.03)

    def multi_click(self, fx, fy, vision, times):
        """Click `times` lần vào cùng một nút (bấm +/- chỉnh số lượng).

        Cú đầu di chuột theo đường cong như click_at; các cú sau chỉ lệch nhẹ
        quanh nút rồi bấm tiếp — giống người giữ chuột tại chỗ bấm liên tiếp.
        """
        if times <= 0:
            return
        self.click_at(fx, fy, vision)
        bx = vision.mon_left + int(fx * vision.W)
        by = vision.mon_top + int(fy * vision.H)
        for _ in range(times - 1):
            time.sleep(0.05 + random.uniform(0.0, 0.09))
            ox, oy = self.human.click_offset(vision.sx) if self.human else (0, 0)
            pydirectinput.moveTo(bx + ox, by + oy)
            time.sleep(0.02 + random.uniform(0.0, 0.03))
            pydirectinput.mouseDown()
            time.sleep(self.human.click_hold() if self.human else 0.04)
            pydirectinput.mouseUp()
