# -*- coding: utf-8 -*-
"""Nhân-hóa thao tác để giống người, giảm khả năng bị anti-cheat gắn cờ hành vi.

Anti-cheat của NTE (ACE) không chặn SendInput, nhưng có thể gắn cờ hành vi
"máy": thời gian phản ứng cố định, nhịp lặp đều tăm tắp, chuột nhảy tức thì,
chạy liên tục nhiều giờ. Module này thêm:
  - thời gian phản ứng ngẫu nhiên (phân phối lệch phải, thỉnh thoảng có "đuôi" chậm)
  - jitter cho thời gian giữ phím / nghỉ giữa các thao tác
  - "mệt mỏi" tăng dần theo thời gian phiên (phản ứng chậm dần như người)
  - nghỉ ngắn ngẫu nhiên (ngó lơ) và thỉnh thoảng nghỉ dài
  - di chuột theo đường cong nhiều bước (Bezier) + lệch điểm click + giữ chuột biến thiên
  - giới hạn thời lượng phiên ngẫu nhiên (tránh treo 24/7)

Tất cả bật/tắt bằng humanize.enabled. Khi tắt, mọi giá trị trả về là mức nền
(không jitter) để tiện gỡ lỗi.
"""
import random
import time


class Humanizer:
    def __init__(self, cfg):
        self.cfg = cfg
        h = cfg.get("humanize", {})
        self.h = h
        self.on = bool(h.get("enabled", True))
        self.rng = random.Random()  # tự seed từ hệ điều hành
        self.start = time.monotonic()
        smin = h.get("session_minutes_min", 0)
        smax = max(smin, h.get("session_minutes_max", 0))
        # 0/thiếu key -> chạy không giới hạn thời lượng phiên
        self.session_limit = (self.rng.uniform(smin, smax) * 60.0
                              if self.on and smax > 0 else None)

    # ---------- mệt mỏi ----------
    def _fatigue(self):
        if not self.on:
            return 0.0
        hours = (time.monotonic() - self.start) / 3600.0
        return min(self.h.get("fatigue_max", 0.6), hours * self.h.get("fatigue_per_hour", 0.25))

    def session_expired(self):
        return self.session_limit is not None and (time.monotonic() - self.start) > self.session_limit

    def session_minutes_left(self):
        if self.session_limit is None:
            return None
        return max(0.0, (self.session_limit - (time.monotonic() - self.start)) / 60.0)

    # ---------- thời gian ----------
    def reaction(self):
        """Độ trễ phản ứng trước khi giật cần (giây) — lệch phải, có đuôi chậm."""
        if not self.on:
            return self.h.get("reaction_min", 0.17)
        lo = self.h.get("reaction_min", 0.17)
        hi = self.h.get("reaction_max", 0.42)
        # trung bình lệch về phía thấp (giống thời gian phản ứng người)
        base = lo + (hi - lo) * (self.rng.random() ** 1.6)
        if self.rng.random() < self.h.get("reaction_tail_chance", 0.12):
            base += self.rng.uniform(0.0, self.h.get("reaction_tail_max", 0.85))
        return base * (1.0 + self._fatigue())

    def hold(self, base):
        """Thời gian giữ phím tap, jitter quanh mức nền."""
        if not self.on:
            return base
        j = self.h.get("hold_jitter", 0.35)
        return max(0.03, base * self.rng.uniform(1.0 - j, 1.0 + j))

    def gap(self, base):
        """Khoảng nghỉ giữa các thao tác (cooldown thả cần...), có cộng mệt mỏi."""
        if not self.on:
            return base
        j = self.h.get("gap_jitter", 0.30)
        return base * self.rng.uniform(1.0 - j, 1.0 + j) * (1.0 + 0.5 * self._fatigue())

    def settle(self, base):
        if not self.on:
            return base
        j = self.h.get("settle_jitter", 0.30)
        return max(0.05, base * self.rng.uniform(1.0 - j, 1.0 + j))

    def fight_start_delay(self):
        if not self.on:
            return 0.0
        return self.rng.uniform(self.h.get("fight_start_delay_min", 0.12),
                                self.h.get("fight_start_delay_max", 0.3)) * (1.0 + self._fatigue())

    def fight_min_hold(self, base):
        if not self.on:
            return base
        j = self.h.get("fight_hold_jitter", 0.25)
        return max(0.05, base * self.rng.uniform(1.0 - j, 1.0 + j))

    # ---------- nghỉ ----------
    def microbreak(self):
        """Thỉnh thoảng trả về số giây nghỉ ngắn (ngó lơ); 0 nếu không nghỉ."""
        if not self.on:
            return 0.0
        if self.rng.random() < self.h.get("longbreak_chance", 0.015):
            return self.rng.uniform(self.h.get("longbreak_min", 15.0),
                                    self.h.get("longbreak_max", 45.0))
        if self.rng.random() < self.h.get("microbreak_chance", 0.06):
            return self.rng.uniform(self.h.get("microbreak_min", 2.0),
                                    self.h.get("microbreak_max", 8.0))
        return 0.0

    # ---------- chuột ----------
    def click_hold(self):
        if not self.on:
            return 0.04
        return self.rng.uniform(self.h.get("click_hold_min", 0.05),
                                self.h.get("click_hold_max", 0.13))

    def click_offset(self, scale=1.0):
        """Lệch điểm click (px) quanh tâm nút, theo phân phối chuẩn."""
        if not self.on:
            return 0, 0
        r = self.h.get("click_jitter_px", 7) * scale
        return int(self.rng.gauss(0, r / 2.0)), int(self.rng.gauss(0, r / 2.0))

    def mouse_path(self, x0, y0, x1, y1):
        """Sinh các điểm trung gian theo đường cong Bezier bậc 2, easing vào/ra.

        Trả về list (x, y, dt) — dt là thời gian ngủ trước mỗi bước.
        """
        if not self.on:
            return [(x1, y1, 0.0)]
        steps = self.rng.randint(self.h.get("mouse_steps_min", 8),
                                 self.h.get("mouse_steps_max", 22))
        dx, dy = x1 - x0, y1 - y0
        dist = max(1.0, (dx * dx + dy * dy) ** 0.5)
        # điểm điều khiển lệch vuông góc với đường thẳng -> đường cong tự nhiên
        curve = self.h.get("mouse_curve", 0.18) * dist * self.rng.uniform(-1, 1)
        nx, ny = -dy / dist, dx / dist
        cx = (x0 + x1) / 2.0 + nx * curve
        cy = (y0 + y1) / 2.0 + ny * curve

        # thỉnh thoảng vọt lố qua đích rồi quay lại
        overshoot = self.rng.random() < self.h.get("mouse_overshoot_chance", 0.25)
        ox, oy = x1, y1
        if overshoot:
            ox = x1 + dx / dist * self.rng.uniform(4, 14)
            oy = y1 + dy / dist * self.rng.uniform(4, 14)

        pts = []
        for i in range(1, steps + 1):
            t = i / steps
            te = 0.5 - 0.5 * __import__("math").cos(t * 3.141592653589793)  # ease in-out
            ex, ey = (ox if overshoot else x1), (oy if overshoot else y1)
            bx = (1 - te) ** 2 * x0 + 2 * (1 - te) * te * cx + te * te * ex
            by = (1 - te) ** 2 * y0 + 2 * (1 - te) * te * cy + te * te * ey
            pts.append((int(round(bx)), int(round(by)), self.rng.uniform(0.004, 0.014)))
        if overshoot:
            pts.append((x1, y1, self.rng.uniform(0.02, 0.05)))
        return pts
