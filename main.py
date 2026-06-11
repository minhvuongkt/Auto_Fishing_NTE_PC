# -*- coding: utf-8 -*-
"""Tool auto câu cá NTE (Neverness to Everness).

Chu trình: thả cần (F) -> chờ cá cắn (vòng xanh quanh nút F) -> F giật cần
-> minigame kéo cá (A/D bám vùng xanh) -> đóng màn kết quả -> lặp lại.

Phím tắt: F8 chạy/tạm dừng, F12 thoát. Chạy PowerShell với quyền Administrator.
"""
import ctypes
import json
import os
import sys
import time

import keyboard
import winsound

from controller import InputController
from fight import FightController
from vision import Vision


def set_dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Bot:
    def __init__(self, cfg):
        self.cfg = cfg
        self.t = cfg["timings"]
        self.keys = cfg["keys"]
        self.vision = Vision(cfg)
        self.inp = InputController(cfg)
        self.fight = FightController(cfg, self.vision, self.inp)

        self.running = True
        self.paused = True
        self._last_paused = None

        self.in_fight = False
        self.fight_started = 0.0
        self.fight_last_seen = 0.0
        self.hooked_at = None
        self.waiting_since = None
        self.last_cast = None
        self.cast_fails = 0
        self.bite_timeouts = 0
        self.catches = 0
        self.fights = 0
        self.last_result_at = 0.0
        self.session_start = time.monotonic()

        # hook thread của keyboard chạy tuần tự cho cả hệ thống: handler chỉ set cờ
        keyboard.add_hotkey(cfg["hotkeys"]["toggle"], self._toggle)
        keyboard.add_hotkey(cfg["hotkeys"]["quit"], self._quit)

    def _toggle(self):
        self.paused = not self.paused

    def _quit(self):
        self.running = False

    def _pause(self, reason):
        log(f"[!] Tạm dừng: {reason} (bấm {self.cfg['hotkeys']['toggle'].upper()} để chạy tiếp)")
        self.paused = True
        self.cast_fails = 0
        self.bite_timeouts = 0

    def stats(self):
        mins = (time.monotonic() - self.session_start) / 60
        return f"đã bắt {self.catches} cá / {self.fights} lần kéo, chạy {mins:.0f} phút"

    def run(self):
        hk = self.cfg["hotkeys"]
        log("=== NTE Auto Fishing ===")
        log(f"Màn hình: {self.vision.W}x{self.vision.H}. "
            f"Đứng tại điểm câu (thấy nút F móc câu) rồi bấm {hk['toggle'].upper()} để bắt đầu.")
        log(f"{hk['toggle'].upper()}: chạy/tạm dừng | {hk['quit'].upper()}: thoát.")
        try:
            while self.running:
                self._tick()
        except KeyboardInterrupt:
            pass
        finally:
            self.inp.release_all()
            keyboard.unhook_all()
            log(f"Kết thúc phiên: {self.stats()}.")

    def _tick(self):
        if self.paused != self._last_paused:
            self._last_paused = self.paused
            self.inp.release_all()
            winsound.Beep(440 if self.paused else 880, 150)
            if self.paused:
                log(f"|| Tạm dừng — {self.stats()}.")
            else:
                log(">> Đang chạy...")
        if self.paused:
            time.sleep(0.15)
            return
        if not self.inp.game_focused():
            self.inp.release_all()
            time.sleep(0.4)
            return

        now = time.monotonic()
        t = self.t

        # 1) Màn kéo cá — ưu tiên cao nhất, vòng lặp nhanh (~60Hz)
        if self.vision.is_fighting():
            if not self.in_fight:
                self.in_fight = True
                self.fights += 1
                self.fight_started = now
                self.hooked_at = None
                self.waiting_since = None
                self.cast_fails = 0
                self.bite_timeouts = 0
                self.fight.reset()
                log(f"(>) Bắt đầu kéo cá (lần {self.fights})...")
            self.fight_last_seen = now
            if now - self.fight_started > t["fight_hard_cap"]:
                log("[!] Màn kéo cá quá lâu — nhả phím, chờ trạng thái mới.")
                self.inp.release_all()
                self.in_fight = False
                time.sleep(1.0)
                return
            self.fight.step()
            time.sleep(t["fight_interval"])
            return

        # 2) Thanh kéo cá vừa biến mất: đợi một nhịp xem kết thúc thật hay chỉ nháy hình
        if self.in_fight:
            if now - self.fight_last_seen < t["fight_end_grace"]:
                self.fight.step()  # vẫn bám theo nếu chỉ mất icon thoáng qua
                time.sleep(t["fight_interval"])
                return
            self.inp.release_all()
            self.in_fight = False
            log("Kéo cá kết thúc — chờ màn kết quả...")

        # 3) Cá cắn câu -> giật cần ngay (cửa sổ phản ứng ngắn)
        if self.vision.is_bite() and (self.hooked_at is None or now - self.hooked_at > 2.0):
            log("(!) Cá cắn câu → F")
            self.inp.tap(self.keys["cast"], t["cast_hold"])
            self.hooked_at = time.monotonic()
            self.waiting_since = None
            time.sleep(0.3)
            return

        # 4) Màn kết quả -> bấm vùng trống để đóng
        if self.vision.is_result():
            # màn kết quả còn hiện sau lần click trước nghĩa là click hụt:
            # chỉ click lại, không đếm trùng con cá
            if now - self.last_result_at > 6.0:
                self.catches += 1
                log(f"<>< Bắt được cá! (tổng: {self.catches})")
                time.sleep(t["result_close_delay"])
            self.last_result_at = time.monotonic()
            fx, fy = self.cfg["click_close_pos"]
            self.inp.click_at(fx, fy, self.vision)
            self.hooked_at = None
            self.waiting_since = None
            time.sleep(t["after_close_delay"])
            return

        # 5) Trạng thái sẵn sàng -> thả cần
        if self.vision.is_idle():
            if self.last_cast is not None and self.waiting_since is not None:
                dt = now - self.last_cast
                if dt < t["cast_cooldown"]:
                    # đang trong animation thả cần, icon chưa kịp ẩn
                    time.sleep(t["scan_interval"])
                    return
                if dt < t["cast_fail_window"]:
                    # vừa bấm F mà UI vẫn ở trạng thái thả cần -> cast không ăn
                    self.cast_fails += 1
                    if self.cast_fails >= t["max_cast_fails"]:
                        self._pause("thả cần không có tác dụng — hết mồi hoặc không ở chế độ câu cá?")
                        return
                else:
                    log("Cá thoát / đứt dây — thả lại.")
            log("Thả cần (F)...")
            self.inp.tap(self.keys["cast"], t["cast_hold"])
            self.last_cast = time.monotonic()
            self.waiting_since = self.last_cast
            self.hooked_at = None
            time.sleep(t["cast_cooldown"])
            return

        # 6) Không nhận diện được gì: đang chờ cá cắn hoặc màn chuyển cảnh
        if self.hooked_at is not None and now - self.hooked_at > t["hook_grace"]:
            # giật cần rồi mà minigame không xuất hiện -> coi như hụt, quay về chờ
            self.hooked_at = None
            if self.waiting_since is None:
                self.waiting_since = now
        if self.waiting_since is not None and now - self.waiting_since > t["bite_timeout"]:
            self.bite_timeouts += 1
            log("Chờ lâu không có cá cắn — thu cần, thả lại.")
            self.inp.tap(self.keys["cast"], t["cast_hold"])
            self.waiting_since = None
            if self.bite_timeouts >= 3:
                self._pause("3 lần liên tiếp không có cá cắn câu.")
                return
            time.sleep(2.0)
            return
        time.sleep(t["scan_interval"])


def app_dir():
    """Thư mục chứa config.json: cạnh file .exe khi đóng gói PyInstaller, cạnh .py khi chạy script."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def main():
    set_dpi_aware()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    cfg_path = os.path.join(app_dir(), "config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if not is_admin():
        print("[!] CẢNH BÁO: chưa chạy quyền Administrator — phím giả lập có thể không tới được game"
              " (HTGame.exe chạy elevated). Hãy mở PowerShell bằng 'Run as Administrator'.")
    Bot(cfg).run()


if __name__ == "__main__":
    main()
