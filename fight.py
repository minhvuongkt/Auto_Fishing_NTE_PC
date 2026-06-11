# -*- coding: utf-8 -*-
"""Bộ điều khiển A/D trong màn kéo cá.

Nguyên tắc (xác nhận từ cơ chế game): vùng xanh = vị trí cá (tự chạy qua lại),
vạch vàng = lưỡi câu. Giữ vạch vàng nằm trong vùng xanh thì "Sức chịu đựng của cá"
giảm dần về 0 -> bắt được. Vạch vàng có QUÁN TÍNH (nhả phím vẫn trôi tiếp) nên:
  - sai số được dự đoán trước: cộng vận tốc vùng xanh (đuổi đón đầu),
    trừ vận tốc con trỏ (phanh sớm để khỏi vọt lố);
  - có dead zone kèm hysteresis (ngưỡng vào > ngưỡng nhả) + thời gian giữ phím
    tối thiểu để khỏi rung phím liên tục.
"""
import time


def _sign(x):
    return 1 if x > 0 else (-1 if x < 0 else 0)


class FightController:
    def __init__(self, cfg, vision, inp):
        self.cfg = cfg
        self.vision = vision
        self.inp = inp
        st = cfg["steering"]
        keys = cfg["keys"]
        self.key_left = keys["pull_left"]
        self.key_right = keys["pull_right"]
        if cfg.get("invert_pull", False):
            self.key_left, self.key_right = self.key_right, self.key_left
        self.min_hold = st["min_hold"]
        self.engage_frac = st["engage_frac"]
        self.release_frac = st["release_frac"]
        self.engage_min_px = st["engage_min_px"]
        self.release_min_px = st["release_min_px"]
        self.green_lookahead = st["green_lookahead"]
        self.marker_brake = st["marker_brake"]
        self.vel_smooth = st["vel_smooth"]
        self.keep_alive = cfg["timings"]["detect_keep_alive"]
        self.reset()

    def reset(self):
        self.last_green = None
        self.last_marker = None
        self.green_seen = 0.0
        self.marker_seen = 0.0
        self.green_vel = 0.0
        self.marker_vel = 0.0
        self.prev_gc = None
        self.prev_marker = None
        self.prev_t = None
        self.hold_since = 0.0

    def step(self):
        """Một nhịp điều khiển. Trả về sai số dự đoán (px) hoặc None nếu mất nhận diện."""
        now = time.monotonic()
        green, marker, bar_w = self.vision.fight_bar()

        # giữ giá trị cũ một lúc khi mất nhận diện thoáng qua (ánh sáng, hiệu ứng...)
        if green is not None:
            self.last_green, self.green_seen = green, now
        elif self.last_green is not None and now - self.green_seen < self.keep_alive:
            green = self.last_green
        if marker is not None:
            self.last_marker, self.marker_seen = marker, now
        elif self.last_marker is not None and now - self.marker_seen < self.keep_alive:
            marker = self.last_marker

        if green is None or marker is None:
            self.inp.release()
            return None

        gc = (green[0] + green[1]) / 2.0
        gw = max(green[1] - green[0], 1.0)

        # cập nhật vận tốc, bỏ qua bước nhảy phi lý (nhiễu nhận diện)
        if self.prev_t is not None:
            dt = now - self.prev_t
            if dt > 0:
                if self.prev_gc is not None and abs(gc - self.prev_gc) < bar_w * 0.5:
                    inst = (gc - self.prev_gc) / dt
                    self.green_vel = self.vel_smooth * self.green_vel + (1 - self.vel_smooth) * inst
                if self.prev_marker is not None and abs(marker - self.prev_marker) < bar_w * 0.5:
                    inst = (marker - self.prev_marker) / dt
                    self.marker_vel = self.vel_smooth * self.marker_vel + (1 - self.vel_smooth) * inst
        self.prev_gc, self.prev_marker, self.prev_t = gc, marker, now

        err = gc - marker
        err_pred = err + self.green_lookahead * self.green_vel - self.marker_brake * self.marker_vel

        sx = self.vision.sx
        engage = max(self.engage_min_px * sx, self.engage_frac * gw)
        release = max(self.release_min_px * sx, self.release_frac * gw)

        held = self.inp.held
        if held is not None:
            cur_dir = 1 if held == self.key_right else -1
            if now - self.hold_since >= self.min_hold:
                if abs(err_pred) <= release or _sign(err_pred) != cur_dir:
                    self.inp.release()
                    # đảo chiều gấp nếu sai số đã lớn về phía ngược lại
                    if _sign(err_pred) != cur_dir and abs(err_pred) > engage:
                        self._hold(_sign(err_pred), now)
        else:
            if abs(err_pred) > engage:
                self._hold(_sign(err_pred), now)
        return err_pred

    def _hold(self, direction, now):
        self.inp.hold(self.key_right if direction > 0 else self.key_left)
        self.hold_since = now
