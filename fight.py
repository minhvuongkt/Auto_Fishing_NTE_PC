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
    def __init__(self, cfg, vision, inp, human=None):
        self.cfg = cfg
        self.vision = vision
        self.inp = inp
        self.human = human
        st = cfg["steering"]
        keys = cfg["keys"]
        self.key_left = keys["pull_left"]
        self.key_right = keys["pull_right"]
        if cfg.get("invert_pull", False):
            self.key_left, self.key_right = self.key_right, self.key_left
        self.min_hold = st["min_hold"]
        self.max_hold = st.get("max_hold", 0.42)
        self.engage_frac = st["engage_frac"]
        self.release_frac = st["release_frac"]
        self.engage_min_px = st["engage_min_px"]
        self.release_min_px = st["release_min_px"]
        self.safe_margin_frac = st.get("safe_margin_frac", 0.18)
        self.hold_until_inside_frac = st.get("hold_until_inside_frac", 0.30)
        self.predict_secs = st.get("predict_secs", st.get("green_lookahead", 0.10))
        self.green_lookahead = st["green_lookahead"]
        self.marker_brake = st["marker_brake"]
        self.marker_vel_brake = st.get("marker_vel_brake", self.marker_brake)
        self.reversal_cooldown = st.get("reversal_cooldown", 0.05)
        self.fast_green_px_per_sec = st.get("fast_green_px_per_sec", 120)
        self.fast_follow_bias_frac = st.get("fast_follow_bias_frac", 0.18)
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
        self.last_release = 0.0
        self.last_switch = 0.0
        self.cur_min_hold = self.min_hold
        # người cần một nhịp để đặt tay lên phím khi trận bắt đầu
        self.ready_at = time.monotonic() + (self.human.fight_start_delay() if self.human else 0.0)

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

        sx = self.vision.sx
        # Mục tiêu không còn là tâm vùng xanh. Vạch vàng chỉ cần nằm trong vùng
        # xanh an toàn; nếu đã nằm đủ sâu thì nhả phím để tránh rung/overshoot.
        margin = min(gw * 0.45, max(self.engage_min_px * sx, gw * self.safe_margin_frac))
        inner_left = green[0] + margin
        inner_right = green[1] - margin
        if inner_left > inner_right:
            inner_left, inner_right = gc - gw * 0.10, gc + gw * 0.10

        release_margin = min(gw * 0.45, max(self.release_min_px * sx, gw * self.hold_until_inside_frac))
        release_left = green[0] + release_margin
        release_right = green[1] - release_margin

        predicted_left = green[0] + self.green_vel * self.predict_secs
        predicted_right = green[1] + self.green_vel * self.predict_secs
        marker_pred = marker + self.marker_vel * self.marker_vel_brake
        fast_thr = max(self.fast_green_px_per_sec * sx, gw * 1.15)
        green_fast = abs(self.green_vel) >= fast_thr
        green_dir = _sign(self.green_vel)

        target = None
        if marker < inner_left:
            target = inner_left
        elif marker > inner_right:
            target = inner_right
        elif marker_pred < predicted_left + margin:
            target = max(inner_left, predicted_left + margin)
        elif marker_pred > predicted_right - margin:
            target = min(inner_right, predicted_right - margin)
        elif green_fast:
            # Chế độ cá chạy nhanh: nếu marker đang ở nửa sau so với hướng chạy
            # của vùng xanh, kéo đón đầu nhẹ. Nếu đã đủ sâu thì đứng im.
            bias = gw * self.fast_follow_bias_frac
            if green_dir > 0 and marker < gc + bias:
                target = min(inner_right, gc + bias)
            elif green_dir < 0 and marker > gc - bias:
                target = max(inner_left, gc - bias)

        if target is None:
            err_pred = 0.0
        else:
            err_pred = target - marker - self.marker_brake * self.marker_vel

        engage = max(self.engage_min_px * sx, self.engage_frac * gw)
        release = max(self.release_min_px * sx, self.release_frac * gw)

        held = self.inp.held
        if held is not None:
            cur_dir = 1 if held == self.key_right else -1
            held_for = now - self.hold_since
            can_release = held_for >= self.cur_min_hold
            inside_release = release_left <= marker <= release_right
            following_fast_green = (
                green_fast and green_dir == cur_dir
                and ((cur_dir > 0 and marker < inner_right) or (cur_dir < 0 and marker > inner_left))
            )
            overshooting = _sign(self.marker_vel) == cur_dir and inside_release and not following_fast_green
            should_release = (
                (inside_release and target is None)
                or (inside_release and not following_fast_green and abs(err_pred) <= release)
                or held_for >= self.max_hold
                or overshooting
                or (_sign(err_pred) != 0 and _sign(err_pred) != cur_dir)
            )
            if can_release and should_release:
                self.inp.release()
                self.last_release = now
                if (_sign(err_pred) != 0 and _sign(err_pred) != cur_dir
                        and abs(err_pred) > engage
                        and now - self.last_switch >= self.reversal_cooldown):
                    self._hold(_sign(err_pred), now)
        else:
            if (target is not None and abs(err_pred) > engage and now >= self.ready_at
                    and now - self.last_release >= self.reversal_cooldown):
                self._hold(_sign(err_pred), now)
        return err_pred

    def _hold(self, direction, now):
        self.inp.hold(self.key_right if direction > 0 else self.key_left)
        self.hold_since = now
        self.last_switch = now
        # mỗi lần giữ phím dài ngắn hơi khác nhau — nhịp bấm không đều tăm tắp
        self.cur_min_hold = self.human.fight_min_hold(self.min_hold) if self.human else self.min_hold
