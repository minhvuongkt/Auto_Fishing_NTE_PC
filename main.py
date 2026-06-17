# -*- coding: utf-8 -*-
"""Tool auto câu cá NTE (Neverness to Everness).

Chu trình: thả cần (F) -> chờ cá cắn (vòng xanh quanh nút F) -> F giật cần
-> tự kéo cá (A/D bám vùng xanh) -> đóng màn kết quả -> lặp lại.
Kèm các luồng phụ: tự bấm F mở bảng khi thấy điểm câu, tự bấm 'Bắt Đầu Câu Cá',
tự bán khoang cá, tự đổi mồi khi hết, tự mua mồi ở shop (R) khi ước tính không
đủ cho chu kỳ câu-bán.

Phím tắt: f10 chạy/tạm dừng, F12 thoát. Chạy PowerShell với quyền Administrator.
"""
import ctypes
import json
import math
import os
import random
import sys
import time

import keyboard
import winsound

from controller import InputController
from fight import FightController
from flows import Flows
from humanizer import Humanizer
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
        self.fl = cfg.get("flows", {})
        self.human = Humanizer(cfg)
        self.vision = Vision(cfg)
        self.inp = InputController(cfg, self.human)
        self.fight = FightController(cfg, self.vision, self.inp, self.human)
        self.flows = Flows(cfg, self.vision, self.inp, log, self._flow_abort, self.human)

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
        self.catches_since_sell = 0
        self.sells = 0
        self.next_sell_at = self._roll_sell_target()
        self.result_wait_since = None
        # sổ mồi nội bộ (tool không đọc được con số trên màn hình):
        # assume_stock > 0 = số mồi đang có lúc khởi động; 0 = chưa biết, chỉ
        # phản ứng khi phát hiện hết sạch. Mỗi lần thả cần trừ 1, mua thêm cộng vào.
        stock = int(self.fl.get("auto_buy_bait", {}).get("assume_stock", 0))
        self.bait_left = stock if stock > 0 else None
        self.baits_bought = 0
        self._bait_exact = stock > 0   # sổ là số tin được (OCR/đã mua) hay chỉ ước lượng
        self._bait_checked_at = 0.0    # lần đọc hộp thoại E gần nhất (chống mở lặp)
        self._bait_watch = True        # tắt nếu nhiều lần không mở được hộp thoại E
        self._bait_read_fails = 0      # số lần liên tiếp không mở/đọc được hộp thoại E
        self._buy_retry_after = 0.0    # nếu shop R không mở nhưng còn mồi, chờ trước khi thử lại
        # bắt buộc đọc số mồi (E) NGAY khi vừa vào chế độ câu, trước lần thả cần đầu
        self._need_bait_check = True
        self._fishing_mode_seen = False  # chỉ check E/cast sau khi đã chắc đang trong chế độ câu
        self._fishing_mode_inferred = False  # True nếu mới chỉ suy từ idle ổn định
        self._idle_since = None           # mốc idle bắt đầu ổn định (chống nhận nhầm world là câu)
        self._enter_attempt_at = 0.0      # chống bấm F mở bảng chuẩn bị liên tục
        self.session_start = time.monotonic()
        self._world_hint_at = 0.0

        # hook thread của keyboard chạy tuần tự cho cả hệ thống: handler chỉ set cờ
        keyboard.add_hotkey(cfg["hotkeys"]["toggle"], self._toggle)
        keyboard.add_hotkey(cfg["hotkeys"]["quit"], self._quit)

    def _toggle(self):
        self.paused = not self.paused

    def _quit(self):
        self.running = False

    def _flow_abort(self):
        return (not self.running) or self.paused or (not self.inp.game_focused())

    def _pause(self, reason):
        # never_pause (mặc định bật): không dừng cứng — tự khôi phục rồi câu tiếp.
        if self.fl.get("never_pause", True):
            self._soft_recover(reason)
            return
        log(f"[!] Tạm dừng: {reason} (bấm {self.cfg['hotkeys']['toggle'].upper()} để chạy tiếp)")
        self.paused = True
        self.cast_fails = 0
        self.bite_timeouts = 0

    def _soft_recover(self, reason):
        """Thay cho dừng cứng: đóng UI về idle, quên sổ mồi để đọc lại, câu tiếp.

        Backoff ngắn tránh spin/log spam khi sự cố lặp (vd hết mồi không mua được):
        các throttle sẵn có (_bait_checked_at, _buy_retry_after, _bait_watch) lo
        phần không mở E/shop liên tục.
        """
        log(f"[~] {reason} — tự khôi phục, tiếp tục câu (không dừng).")
        self.cast_fails = 0
        self.bite_timeouts = 0
        self.flows.recover_to_idle()
        # quên sổ mồi: lần idle kế đọc lại E thay vì tin con số có thể đã sai
        self.bait_left = None
        self._bait_exact = False
        self._need_bait_check = True
        self.last_cast = None
        self.waiting_since = None
        self.hooked_at = None
        time.sleep(1.5)

    def _enter_fishing_from_world(self, now):
        """Đứng trước điểm câu: bấm F mở bảng chuẩn bị rồi bấm Bắt Đầu.

        Đây là cổng vào bắt buộc trước khi cho phép check mồi/cast. Không dùng
        is_idle để tự suy luận vì world/prep có nhiều UI trắng dễ false-positive.
        """
        self._fishing_mode_seen = False
        self._need_bait_check = False
        self._idle_since = None
        if not self.fl.get("auto_enter_fishing", True):
            if now - self._world_hint_at > 15.0:
                self._world_hint_at = now
                log("Thấy điểm câu — auto_enter_fishing đang tắt, hãy bấm F mở bảng câu cá.")
            return False
        if now - self._enter_attempt_at < 3.0:
            return False
        self._enter_attempt_at = now
        log("Thấy điểm câu — bấm F mở bảng chuẩn bị câu cá...")
        self.inp.tap(self.keys["cast"], self.t["cast_hold"])
        end = time.monotonic() + 4.0
        while time.monotonic() < end:
            if self._flow_abort():
                return False
            if self.vision.is_prepare_panel():
                if self.flows.start_from_prepare():
                    self._fishing_mode_seen = True
                    self._fishing_mode_inferred = False
                    self._need_bait_check = True
                    self._idle_since = None
                    return True
                return False
            time.sleep(0.1)
        log("[!] Đã bấm F nhưng chưa thấy bảng chuẩn bị câu cá.")
        return False

    def _roll_sell_target(self):
        """Mốc bán ngẫu nhiên — số cá giữa 2 lần bán không cố định để khỏi thành nhịp đều."""
        sell = self.cfg["flows"].get("auto_sell", {})
        lo = int(sell.get("every_catches_min", sell.get("every_catches", 20)))
        hi = int(sell.get("every_catches_max", round(lo * 1.5)))
        if hi < lo:
            lo, hi = hi, lo
        return random.randint(lo, hi)

    def stats(self):
        mins = (time.monotonic() - self.session_start) / 60
        s = f"đã bắt {self.catches} cá / {self.fights} lần kéo"
        if self.sells:
            s += f", {self.sells} lần bán khoang"
        if self.baits_bought:
            s += f", đã mua {self.baits_bought} mồi"
        if self.bait_left is not None:
            s += f", ~{self.bait_left} mồi còn lại"
        return s + f", chạy {mins:.0f} phút"

    def run(self):
        hk = self.cfg["hotkeys"]
        log("=== NTE Auto Fishing ===")
        log(f"Màn hình: {self.vision.W}x{self.vision.H}. "
            f"Đứng tại/gần điểm câu rồi bấm {hk['toggle'].upper()} để bắt đầu.")
        log(f"Bán khoang sau khoảng {self.next_sell_at} cá.")
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
                # f10 chạy tiếp: chỉ đọc lại mồi nếu trước đó đã xác nhận đang ở chế độ câu.
                # Nếu mới đứng ngoài điểm câu/đang ở bảng chuẩn bị thì phải vào flow đó trước.
                self._need_bait_check = self._fishing_mode_seen
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
            self._fishing_mode_seen = True
            self._fishing_mode_inferred = False
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
            self.result_wait_since = now
            log("Kéo cá kết thúc — chờ màn kết quả...")

        # 3) Cá cắn câu -> giật cần ngay (cửa sổ phản ứng ngắn, có độ trễ giống người)
        if self.vision.is_bite() and self.hooked_at is None:
            self._fishing_mode_seen = True
            self._fishing_mode_inferred = False
            rt = self.human.reaction()
            log(f"(!) Cá cắn câu → F (phản ứng {rt*1000:.0f}ms)")
            time.sleep(rt)
            if not self.vision.is_bite():
                # cá nhả mất trong lúc "phản ứng" — bỏ qua nhịp này
                return
            self.inp.tap(self.keys["cast"], t["cast_hold"])
            self.hooked_at = time.monotonic()
            self.waiting_since = None
            time.sleep(self.human.settle(0.3))
            return

        # 4) Màn kết quả -> bấm vùng trống để đóng
        if self.vision.is_result():
            self._fishing_mode_seen = True
            self._fishing_mode_inferred = False
            self.result_wait_since = None
            self.catches += 1
            self.catches_since_sell += 1
            log(f"<>< Bắt được cá! (tổng: {self.catches}, khoang: {self.catches_since_sell}/{self.next_sell_at})")
            time.sleep(self.human.settle(t["result_close_delay"]))
            fx, fy = self.cfg["click_close_pos"]
            self.inp.click_at(fx, fy, self.vision)
            self.hooked_at = None
            self.waiting_since = None
            time.sleep(self.human.gap(t["after_close_delay"]))
            self._maybe_break()  # nghỉ ngẫu nhiên: chỉ roll 1 lần mỗi con cá, tránh thành nhịp đều
            return

        if self.result_wait_since is not None and now - self.result_wait_since > 5.0:
            # Detector màn kết quả đôi khi miss khi hiệu ứng/ánh sáng thay đổi. Nếu vừa
            # kéo cá xong mà chưa về idle/fight/bite sau vài giây, click đóng thử để
            # tránh kẹt. Tính là một cá vì đây là nhánh chỉ xảy ra sau fight kết thúc.
            log("[!] Chờ màn kết quả quá lâu — click đóng fallback và tính 1 cá.")
            fx, fy = self.cfg["click_close_pos"]
            self.inp.click_at(fx, fy, self.vision)
            self.result_wait_since = None
            self.catches += 1
            self.catches_since_sell += 1
            log(f"<>< Bắt được cá? fallback (tổng: {self.catches}, khoang: {self.catches_since_sell}/{self.next_sell_at})")
            self.hooked_at = None
            self.waiting_since = None
            self.last_cast = None
            time.sleep(self.human.gap(t["after_close_delay"]))
            return

        # 5) Màn ngoài chế độ câu phải xử lý trước IDLE: icon/phím trắng ở world/prep
        # có thể rơi vào ROI idle_e_icon, nếu check E/cast ngay sẽ sai flow.
        if self.vision.is_world_prompt():
            self._enter_fishing_from_world(now)
            time.sleep(t["scan_interval"])
            return

        if self.vision.is_prepare_panel():
            if self.fl.get("auto_enter_fishing", True):
                if self.flows.start_from_prepare():
                    self._fishing_mode_seen = True
                    self._fishing_mode_inferred = False
                    # vừa vào chế độ câu -> kiểm tra mồi (E) trước khi thả cần
                    self._need_bait_check = True
            time.sleep(0.5)
            return

        # 6) Trạng thái sẵn sàng -> thả cần (kèm các luồng phụ)
        if self.vision.is_idle():
            if not self._fishing_mode_seen:
                # CẤM suy luận chế độ câu từ idle. Chỉ cho phép vào flow câu khi đã có
                # bằng chứng mạnh: start_from_prepare thành công, hoặc bite/fight/result.
                # Nếu detector world/prep còn lệch thì thà đứng yên còn hơn check mồi sai.
                if now - self._world_hint_at > 5.0:
                    self._world_hint_at = now
                    v = self.vision
                    wp = v.count_roi("world_prompt", "pink_ui")
                    pw = v.count_roi("prepare_button", "white")
                    iw = v.count_roi("idle_e_icon", "white")
                    log("[?] idle chưa xác nhận câu | "
                        f"world_pink={wp:.0f}/{v.t('world_pink_px'):.0f} "
                        f"prep_white={pw:.0f}/{v.t('prepare_white_px'):.0f} "
                        f"idle_white={iw:.0f}/{v.t('idle_white_px'):.0f} "
                        f"| world={v.is_world_prompt()} prep={v.is_prepare_panel()}")
                time.sleep(t["scan_interval"])
                return
            self._idle_since = None  # đã xác nhận, reset mốc cho lần ra/vào sau
            # hết thời lượng phiên ngẫu nhiên -> dừng tại điểm an toàn (chưa thả cần mới)
            if self.human.session_expired() and self.waiting_since is None:
                self._pause("đã đạt thời lượng phiên ngẫu nhiên (an toàn trước anti-cheat) — "
                            "bấm f10 nếu muốn chạy tiếp")
                self.human.start = time.monotonic()  # f10 chạy tiếp sẽ tính phiên mới
                return
            ready = self.last_cast is None or now - self.last_cast >= t["cast_cooldown"]
            sell = self.fl.get("auto_sell", {})
            if (ready and self.cast_fails == 0 and sell.get("enabled", False)
                    and self.catches_since_sell >= self.next_sell_at):
                if self.flows.sell_fish():
                    self.sells += 1
                    self.catches_since_sell = 0
                    self.next_sell_at = self._roll_sell_target()
                    log(f"Lần bán tiếp theo: sau {self.next_sell_at} con nữa.")
                self.last_cast = None
                self.waiting_since = None
                time.sleep(0.5)
                return
            # trước khi thả cần: đọc số mồi còn lại (E), thiếu cho chu kỳ bán kế
            # tiếp thì vào shop (R) mua trước. Vừa vào chế độ câu là đọc 1 lần.
            buyb = self.fl.get("auto_buy_bait", {})
            if ready and self.cast_fails == 0 and buyb.get("enabled", False):
                if (self._need_bait_check or self.bait_left is None) and self._bait_watch:
                    # đọc chính xác số mồi của ô đang dùng (OCR) trước khi thả cần
                    self._need_bait_check = False
                    self._refresh_bait_count()
                    return
                if self.bait_left is not None and self.bait_left < self._bait_needed():
                    # sổ không chắc (OCR trượt) và đã cạn -> đọc lại E trước khi mua
                    if (not self._bait_exact and self.bait_left <= 0
                            and time.monotonic() - self._bait_checked_at > 30.0):
                        self._refresh_bait_count()
                        return
                    if self.bait_left > 0 and time.monotonic() < self._buy_retry_after:
                        # Vẫn còn mồi để câu; lần mở shop trước thất bại nên không kẹt
                        # ở vòng mua lại liên tục.
                        pass
                    else:
                        log(f"Mồi còn {self.bait_left}, cần {self._bait_needed()} cho chu kỳ bán — đi mua mồi.")
                        self._buy_bait()
                        return
            else:
                self._need_bait_check = False  # auto_buy tắt: không giữ cờ kẹt
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
                        self._handle_no_bait()
                        return
                else:
                    log("Cá thoát / đứt dây — thả lại.")
            log("Thả cần (F)...")
            self.inp.tap(self.keys["cast"], t["cast_hold"])
            if self.bait_left is not None:
                self.bait_left = max(0, self.bait_left - 1)  # mỗi lần thả cần tốn 1 mồi
            self.last_cast = time.monotonic()
            self.waiting_since = self.last_cast
            self.hooked_at = None
            time.sleep(self.human.gap(t["cast_cooldown"]))
            return

        # 7) Không nhận diện được gì: chờ cá cắn, màn chuyển cảnh, hoặc đang ở ngoài chế độ câu
        if self.waiting_since is None and self.hooked_at is None and not self.in_fight:
            if self.fl.get("auto_enter_fishing", True) and self.vision.is_prepare_panel():
                if self.flows.start_from_prepare():
                    self._fishing_mode_seen = True
                    self._need_bait_check = True
                return
            if self.vision.is_world_prompt():
                self._enter_fishing_from_world(now)
                return
            if (self.vision.is_master_ui() or self.vision.is_dialog()
                    or self.vision.is_bait_dialog() or self.vision.is_bait_shop()):
                log("UI shop/hộp thoại đang mở ngoài luồng — tự đóng...")
                self.flows.recover_to_idle()
                return
        if self.hooked_at is not None and now - self.hooked_at > t["hook_grace"]:
            # giật cần rồi mà minigame không xuất hiện -> coi như hụt, quay về chờ
            self.hooked_at = None
            if self.waiting_since is None:
                self.waiting_since = now
        if self.waiting_since is not None and now - self.waiting_since > t["bite_timeout"]:
            self.bite_timeouts += 1
            log("Chờ lâu không có cá cắn — thu cần, thả lại.")
            self.inp.tap(self.keys["cast"], t["cast_hold"])
            if self.bait_left is not None:
                self.bait_left = max(0, self.bait_left - 1)  # thả lại cũng tốn 1 mồi
            self.waiting_since = None
            if self.bite_timeouts >= 3:
                self._pause("3 lần liên tiếp không có cá cắn câu.")
                return
            time.sleep(2.0)
            return
        time.sleep(t["scan_interval"])

    def _maybe_break(self):
        br = self.human.microbreak()
        if br <= 0:
            return
        self.inp.release_all()
        log(f"(~) Nghỉ ngẫu nhiên {br:.0f}s cho giống người...")
        end = time.monotonic() + br
        while time.monotonic() < end:
            if self.paused or not self.running:
                return
            time.sleep(0.2)

    def _handle_no_bait(self):
        """Thả cần liên tục không ăn — nghi hết mồi: đổi mồi, hết sạch thì tự mua."""
        self.cast_fails = 0
        if self.fl.get("auto_switch_bait", True):
            res = self.flows.switch_bait()
            if res == "switched":
                # sang loại mồi khác, chưa rõ số lượng -> ước lượng lại ở lần idle kế
                self.bait_left = None
                self._bait_exact = False
                self.waiting_since = None
                self.last_cast = None
                return
            if res == "bait_ok":
                self._pause("thả cần không có tác dụng nhưng mồi vẫn còn — kiểm tra game rồi chạy tiếp")
                return
            if res == "empty":
                if self.fl.get("auto_buy_bait", {}).get("enabled", False):
                    log("Hết sạch mọi loại mồi — thử tự mua ở shop (R)...")
                    self.bait_left = 0
                    self._bait_exact = True
                    self._buy_bait()
                    # mồi mới mua có thể chưa được gắn: lần thả hụt kế tiếp sẽ
                    # kích hoạt đổi mồi và tự chọn đúng loại vừa mua
                    return
                self._pause("đã HẾT SẠCH mọi loại mồi — mua thêm ở shop (phím R) rồi chạy tiếp")
                return
            if res == "failed":
                self.bait_left = None
                self._bait_exact = False
                self._need_bait_check = True
                self.waiting_since = None
                self.last_cast = None
                log("Chưa xác nhận được hết mồi — sẽ đọc lại hộp thoại E, không mua vội.")
                return
        self._pause("thả cần không có tác dụng — hết mồi hoặc không ở chế độ câu cá?")

    def _bait_needed(self):
        """Số mồi cần có: đủ câu số cá còn lại tới lần bán kế tiếp (theo auto sell)."""
        sell = self.fl.get("auto_sell", {})
        if sell.get("enabled", False):
            return max(1, self.next_sell_at - self.catches_since_sell)
        return 5  # không bật auto_sell: chỉ cần giữ một mức đệm nhỏ

    def _refresh_bait_count(self):
        """Đọc CHÍNH XÁC số mồi của ô đang chọn qua hộp thoại E (OCR).

        Dùng trước khi câu (vừa vào chế độ câu) và khi sổ cạn. Mở được hộp thoại
        nhưng OCR trượt số thì giữ has_stock thô (còn/hết) làm dự phòng. Chỉ tắt
        theo dõi sau vài lần liên tiếp KHÔNG mở được hộp thoại (E hỏng thật sự).
        """
        self._bait_checked_at = time.monotonic()
        res = self.flows.check_bait_level()
        self.last_cast = None
        self.waiting_since = None
        if res == "ambiguous_stock":
            self._bait_read_fails = 0
            # Đã đọc được hộp thoại và thấy còn ít nhất một loại mồi, chỉ trượt
            # viền chọn. Không tính là lỗi E, để lần sau vẫn kiểm tra lại được.
            self.bait_left = self._bait_needed()
            self._bait_exact = False
            log("Không xác định được ô mồi đang dùng nhưng vẫn thấy còn mồi — tạm coi là đủ.")
            return
        if res == "ambiguous_empty":
            self._bait_read_fails = 0
            self.bait_left = 0
            self._bait_exact = True
            log("Không xác định được ô mồi đang dùng nhưng toàn bộ ô đã đọc đều hết — chuẩn bị đổi/mua mồi.")
            self._handle_empty_bait()
            return
        if res is None:
            self._bait_read_fails += 1
            if self._fishing_mode_inferred:
                # Vừa chỉ suy từ idle mà E không mở được -> nhiều khả năng chưa vào
                # chế độ câu thật. Rút lại xác nhận này, quay về quan sát world/prep.
                self._fishing_mode_seen = False
                self._fishing_mode_inferred = False
                self._need_bait_check = False
                self._idle_since = None
                self.bait_left = None
                self._bait_exact = False
                log("[!] Mở E thất bại ngay sau xác nhận bằng idle — hủy xác nhận chế độ câu, chờ detect lại.")
                return
            if self._bait_read_fails >= 3:
                self._bait_watch = False
                log("[!] Nhiều lần không mở được hộp thoại mồi — tạm bỏ theo dõi, "
                    "chỉ tự mua khi phát hiện hết sạch.")
            else:
                log("[!] Lần này không mở/đọc được hộp thoại mồi — thử lại sau.")
            # Không retry E liên tục trong cùng một trạng thái idle; nếu không sẽ
            # tự đếm 3 lỗi liên tiếp chỉ vì UI mở chậm/nhận diện chập chờn.
            self.bait_left = self._bait_needed()
            self._bait_exact = False
            return
        self._bait_read_fails = 0
        has_stock, count = res
        if count is not None:
            max_count = int(self.fl.get("auto_buy_bait", {}).get("max_reasonable_stock", 999))
            if count > max_count:
                self.bait_left = self._bait_needed()
                self._bait_exact = False
                log(f"[!] OCR đọc số mồi phi lý ({count} > {max_count}) — bỏ số này, tạm coi là đủ và sẽ đọc lại sau.")
                return
            # OCR ra số thật -> sổ chính xác
            self.bait_left = count
            self._bait_exact = True
            if count <= 0:
                log("Ô mồi đang chọn đã HẾT (0) — chuẩn bị đổi/mua mồi.")
                self._handle_empty_bait()
            else:
                log(f"Số mồi hiện tại: {count} (cần {self._bait_needed()} cho chu kỳ bán).")
            return
        # mở được hộp thoại nhưng OCR không ra số -> dùng has_stock thô
        if not has_stock:
            self.bait_left = 0
            self._bait_exact = True
            log("Ô mồi đang chọn báo HẾT — chuẩn bị đổi/mua mồi.")
            self._handle_empty_bait()
        else:
            self.bait_left = self._bait_needed()  # còn hàng, chưa rõ bao nhiêu -> coi là đủ
            self._bait_exact = False
            log("Ô mồi còn hàng nhưng không đọc được con số — tạm coi là đủ.")

    def _handle_empty_bait(self):
        """Khi check E xác nhận mồi đang dùng đã hết: ưu tiên đổi loại còn hàng, rồi mới mua."""
        if self.fl.get("auto_switch_bait", True):
            res = self.flows.switch_bait()
            if res == "switched":
                self.bait_left = None
                self._bait_exact = False
                self._need_bait_check = True
                self.last_cast = None
                self.waiting_since = None
                return
            if res == "bait_ok":
                self.bait_left = self._bait_needed()
                self._bait_exact = False
                log("Hộp thoại đổi mồi báo mồi đang dùng vẫn còn — tạm coi là đủ.")
                return
            if res == "empty":
                if self.fl.get("auto_buy_bait", {}).get("enabled", False):
                    log("Hết sạch mọi loại mồi — thử tự mua ở shop (R)...")
                    self._buy_bait()
                    return
                self._pause("đã HẾT SẠCH mọi loại mồi — mua thêm ở shop (phím R) rồi chạy tiếp")
                return
            if res == "failed":
                self.bait_left = None
                self._bait_exact = False
                self._need_bait_check = True
                self.last_cast = None
                self.waiting_since = None
                log("Chưa đổi được mồi — sẽ đọc lại hộp thoại E trước khi quyết định mua.")
                return
        if self.fl.get("auto_buy_bait", {}).get("enabled", False):
            self._buy_bait()
        else:
            self._pause("mồi đang dùng đã hết — đổi/mua mồi rồi chạy tiếp")

    def _buy_bait(self):
        """Chạy flow mua mồi rồi cập nhật sổ mồi; mua hỏng thì tạm dừng chờ người xử lý."""
        buyb = self.fl.get("auto_buy_bait", {})
        have = self.bait_left or 0
        amount = int(buyb.get("buy_amount", 0))
        if amount <= 0:
            # tự tính theo auto sell: bù cho đủ tới lần bán kế + 20% hao hụt
            # (cá sẩy / chờ quá lâu vẫn tốn mồi mà không ra cá)
            amount = math.ceil((self._bait_needed() - have) * 1.2)
        bought = self.flows.buy_bait(amount)
        if bought > 0:
            self._buy_retry_after = 0.0
            self.bait_left = have + bought
            self.baits_bought += bought
            # Mua xong chỉ là sổ tính toán. Lần idle kế tiếp phải mở E đọc OCR
            # xác nhận số thật, tránh lệch nếu shop mua không đúng như flow nghĩ.
            self._bait_exact = False
            self._need_bait_check = True
            log(f"Sổ mồi sau khi mua (chờ OCR xác nhận): ~{self.bait_left}.")
        else:
            if have > 0:
                self.bait_left = have
                self._buy_retry_after = time.monotonic() + 90.0
                log(f"[!] Không mua được mồi nhưng vẫn còn ~{have} mồi — tiếp tục câu, thử mua lại sau.")
            else:
                self._pause("không mua được mồi (hết sò? shop lệch config?) — xử lý tay rồi chạy tiếp")
        self.last_cast = None
        self.waiting_since = None
        time.sleep(0.5)


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
