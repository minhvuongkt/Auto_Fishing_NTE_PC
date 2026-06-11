# -*- coding: utf-8 -*-
"""Đọc màn hình & nhận diện trạng thái câu cá NTE bằng lọc màu HSV trên các ROI nhỏ.

Mọi ROI lưu dạng tỉ lệ (x, y, w, h chia cho 1920x1080) nên tự co giãn theo độ
phân giải thật của màn hình chính.
"""
import numpy as np
import cv2
import mss

BASE_W, BASE_H = 1920.0, 1080.0


def longest_run(flags):
    """Tìm đoạn True liên tục dài nhất trong mảng 1 chiều. Trả về (x0, x1) hoặc None."""
    best = None
    start = None
    n = len(flags)
    for i in range(n + 1):
        v = flags[i] if i < n else False
        if v and start is None:
            start = i
        elif not v and start is not None:
            if best is None or (i - start) > (best[1] - best[0]):
                best = (start, i)
            start = None
    return best


def _new_mss():
    # mss >= 10 đổi mss.mss thành mss.MSS (tên cũ gây DeprecationWarning)
    return getattr(mss, "MSS", mss.mss)()


class Vision:
    def __init__(self, cfg):
        self.cfg = cfg
        self.sct = _new_mss()
        mon = self.sct.monitors[1]
        self.mon_left, self.mon_top = mon["left"], mon["top"]
        self.W, self.H = mon["width"], mon["height"]
        self.sx = self.W / BASE_W
        self.area_scale = (self.W * self.H) / (BASE_W * BASE_H)
        self.hsv = {
            name: (np.array(lo, dtype=np.uint8), np.array(hi, dtype=np.uint8))
            for name, (lo, hi) in cfg["hsv"].items()
        }
        self.thr = cfg["thresholds"]

    # ---------- tiện ích ----------
    def roi_px(self, name):
        """ROI -> (left, top, w, h) theo pixel tuyệt đối trên màn hình chính."""
        rx, ry, rw, rh = self.cfg["rois"][name]
        return (self.mon_left + int(rx * self.W), self.mon_top + int(ry * self.H),
                max(1, int(rw * self.W)), max(1, int(rh * self.H)))

    def grab(self, name):
        x, y, w, h = self.roi_px(name)
        raw = self.sct.grab({"left": x, "top": y, "width": w, "height": h})
        return cv2.cvtColor(np.asarray(raw), cv2.COLOR_BGRA2BGR)

    def mask(self, bgr, color):
        lo, hi = self.hsv[color]
        return cv2.inRange(cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV), lo, hi)

    def count(self, bgr, color):
        return int(cv2.countNonZero(self.mask(bgr, color)))

    def t(self, key):
        """Ngưỡng đếm pixel, co giãn theo diện tích màn hình so với 1080p."""
        return self.thr[key] * self.area_scale

    # ---------- nhận diện trạng thái ----------
    def is_bite(self):
        """Cá cắn câu: vòng sáng xanh dương quanh nút F (góc phải dưới)."""
        return self.count(self.grab("bite_f_ring"), "bite_blue") > self.t("bite_blue_px")

    def is_fighting(self):
        """Đang kéo cá: 2 icon tròn (viền vàng trái + viền cyan phải) trên đầu màn hình."""
        if self.count(self.grab("fight_left_icon"), "gold_ring") < self.t("fight_ring_px"):
            return False
        return self.count(self.grab("fight_right_icon"), "cyan_ring") > self.t("fight_ring_px")

    def is_idle(self):
        """Sẵn sàng thả cần: icon E (đổi mồi) màu trắng còn hiện ở góc phải dưới."""
        return self.count(self.grab("idle_e_icon"), "white") > self.t("idle_white_px")

    def is_result(self):
        """Màn kết quả: vòng tròn trắng lớn giữa màn hình + khung 'Cấp Câu Cá' tối phía trên."""
        if self.count(self.grab("result_circle"), "white") < self.t("result_white_px"):
            return False
        cap = self.grab("result_capsule")
        dark = self.count(cap, "dark")
        return dark > cap.shape[0] * cap.shape[1] * self.thr["capsule_dark_frac"]

    def fight_bar(self):
        """Phân tích thanh kéo cá trên đầu màn hình.

        Trả về (green, marker_x, bar_w):
          green    : (x0, x1) vùng xanh lá — vị trí cá (px trong ROI) hoặc None
          marker_x : tọa độ x con trỏ vàng — lưỡi câu (px trong ROI) hoặc None
          bar_w    : bề rộng ROI (px)
        """
        bgr = self.grab("fight_bar")
        h, w = bgr.shape[:2]
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

        glo, ghi = self.hsv["green_zone"]
        gmask = cv2.inRange(hsv, glo, ghi)
        cols = (gmask > 0).sum(axis=0)
        need = max(1, int(h * self.thr["green_col_frac"]))
        green = longest_run(cols >= need)
        if green is not None and (green[1] - green[0]) < self.thr["green_min_width_px"] * self.sx:
            green = None

        ylo, yhi = self.hsv["yellow_marker"]
        ymask = cv2.inRange(hsv, ylo, yhi)
        ycols = (ymask > 0).sum(axis=0).astype(np.float64)
        marker = None
        if ycols.max() > 0:
            # con trỏ là một vạch dọc mảnh: lấy trọng tâm quanh cột đậm nhất
            peak = int(np.argmax(ycols))
            half = max(4, int(8 * self.sx))
            x0, x1 = max(0, peak - half), min(w, peak + half + 1)
            window = ycols[x0:x1]
            if window.sum() >= self.thr["marker_min_px"] * self.sx:
                xs = np.arange(x0, x1, dtype=np.float64)
                marker = float((xs * window).sum() / window.sum())
        return green, marker, w
