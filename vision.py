# -*- coding: utf-8 -*-
"""Đọc màn hình & nhận diện trạng thái câu cá NTE bằng lọc màu HSV trên các ROI nhỏ.

Mọi ROI lưu dạng tỉ lệ (x, y, w, h chia cho 1920x1080) nên tự co giãn theo độ
phân giải thật của màn hình chính (chuẩn nhất với màn 16:9).
"""
import time

import numpy as np
import cv2
import mss

import ocr

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
        # cache 1 khung toàn màn cho mỗi nhịp dò: gộp ~10 lần chụp ROI lẻ/ tick
        # thành 1 lần chụp. TTL ngắn nên các is_X() trong cùng nhịp dùng chung
        # frame (cùng thời điểm), còn qua mỗi sleep sẽ tự chụp lại frame mới.
        self._frame = None
        self._frame_t = 0.0
        self._frame_ttl = float(cfg["timings"].get("frame_cache_ttl", 0.012))
        self._mon = {"left": self.mon_left, "top": self.mon_top,
                     "width": self.W, "height": self.H}

    # ---------- tiện ích ----------
    def roi_px(self, name):
        rx, ry, rw, rh = self.cfg["rois"][name]
        return (self.mon_left + int(rx * self.W), self.mon_top + int(ry * self.H),
                max(1, int(rw * self.W)), max(1, int(rh * self.H)))

    def _full_frame(self):
        """Khung BGR toàn màn, cache theo TTL để tái dùng trong cùng nhịp dò."""
        now = time.monotonic()
        if self._frame is None or now - self._frame_t >= self._frame_ttl:
            raw = self.sct.grab(self._mon)
            self._frame = cv2.cvtColor(np.asarray(raw), cv2.COLOR_BGRA2BGR)
            self._frame_t = now
        return self._frame

    def grab_rect(self, rect):
        """Cắt một vùng theo tỉ lệ [x, y, w, h] từ khung toàn màn đã cache."""
        rx, ry, rw, rh = rect
        frame = self._full_frame()
        x0 = max(0, int(rx * self.W))
        y0 = max(0, int(ry * self.H))
        x1 = min(self.W, x0 + max(1, int(rw * self.W)))
        y1 = min(self.H, y0 + max(1, int(rh * self.H)))
        return frame[y0:y1, x0:x1]

    def grab(self, name):
        return self.grab_rect(self.cfg["rois"][name])

    def grab_rect_direct(self, rect):
        """Chụp thẳng một vùng nhỏ (không qua cache toàn màn) — dùng cho vòng kéo
        cá ~60Hz: chỉ cần đúng 1 ROI thanh kéo, chụp vùng nhỏ rẻ hơn cả màn."""
        rx, ry, rw, rh = rect
        raw = self.sct.grab({
            "left": self.mon_left + int(rx * self.W),
            "top": self.mon_top + int(ry * self.H),
            "width": max(1, int(rw * self.W)),
            "height": max(1, int(rh * self.H)),
        })
        return cv2.cvtColor(np.asarray(raw), cv2.COLOR_BGRA2BGR)

    def mask(self, bgr, color):
        lo, hi = self.hsv[color]
        return cv2.inRange(cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV), lo, hi)

    def count(self, bgr, color):
        return int(cv2.countNonZero(self.mask(bgr, color)))

    def count_roi(self, roi_name, color):
        return self.count(self.grab(roi_name), color)

    def dark_frac(self, roi_name):
        img = self.grab(roi_name)
        return self.count(img, "dark") / float(img.shape[0] * img.shape[1])

    def t(self, key):
        """Ngưỡng đếm pixel, tự co giãn theo diện tích màn hình so với 1080p."""
        return self.thr[key] * self.area_scale

    # ---------- vòng lặp câu chính ----------
    def is_bite(self):
        return self.count_roi("bite_f_ring", "bite_blue") > self.t("bite_blue_px")

    def is_fighting(self):
        if self.count_roi("fight_left_icon", "gold_ring") < self.t("fight_ring_px"):
            return False
        return self.count_roi("fight_right_icon", "cyan_ring") > self.t("fight_ring_px")

    def is_idle(self):
        # 1 grab duy nhất cho nhanh. False-positive ở world/prepare không còn hại
        # vì _tick check world/prepare TRƯỚC idle, và idle không tự nhận fishing-mode.
        return self.count_roi("idle_e_icon", "white") > self.t("idle_white_px")

    def is_result(self):
        if self.count_roi("result_circle", "white") < self.t("result_white_px"):
            return False
        return self.dark_frac("result_capsule") > self.thr["capsule_dark_frac"]

    def fight_bar(self):
        """Phân tích thanh kéo cá.
        Trả về (green, marker_x, bar_w):
          green   : (x0, x1) vùng xanh (px trong ROI) hoặc None
          marker_x: tọa độ x vạch vàng (px trong ROI) hoặc None
          bar_w   : bề rộng ROI (px)
        """
        bgr = self.grab_rect_direct(self.cfg["rois"]["fight_bar"])
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
            peak = int(np.argmax(ycols))
            half = max(4, int(8 * self.sx))
            x0, x1 = max(0, peak - half), min(w, peak + half + 1)
            window = ycols[x0:x1]
            if window.sum() >= self.thr["marker_min_px"] * self.sx:
                xs = np.arange(x0, x1, dtype=np.float64)
                marker = float((xs * window).sum() / window.sum())
        return green, marker, w

    # ---------- ngoài chế độ câu ----------
    def is_world_prompt(self):
        """Nhãn hồng 'Câu cá' ngoài thế giới (đứng gần điểm câu)."""
        return self.count_roi("world_prompt", "pink_ui") >= self.t("world_pink_px")

    def is_prepare_panel(self):
        """Bảng 'Chuẩn bị câu cá' với nút trắng lớn 'Bắt Đầu Câu Cá'.

        Nút trắng là tín hiệu chính (icon E lúc idle chỉ cho vài trăm px trắng,
        không thể chạm ngưỡng này). Nền tối phía trên chỉ dùng để vớt khi nút
        thiếu sáng — panel mờ/trời sáng làm dark_frac không đạt nên không được
        bắt buộc cả hai như trước.
        """
        white = self.count_roi("prepare_button", "white")
        if white >= self.t("prepare_white_px"):
            return True
        return (white >= self.t("prepare_white_px") * 0.5
                and self.dark_frac("prepare_top") > self.thr["prepare_dark_frac"])

    # ---------- shop / hộp thoại ----------
    def is_master_ui(self):
        """Cửa sổ FISHING MASTER (Chợ Cá / Khoang cá) — dải tiêu đề cam."""
        return self.count_roi("master_header", "orange_ui") > self.t("master_orange_px")

    def is_storage_page(self):
        """Đang ở trang Khoang cá: có nút BÁN NHANH dạng pill đen chữ trắng."""
        if not self.is_master_ui():
            return False
        roi = self.grab("storage_sell_btn")
        white = self.count(roi, "white")
        dark = self.count(roi, "dark") / float(max(1, roi.shape[0] * roi.shape[1]))
        return (white > self.t("sell_btn_white_px")
                and dark > self.thr.get("sell_btn_dark_frac", 0.45))

    def storage_debug(self):
        """Số đo live cho detector Khoang cá / nút BÁN NHANH."""
        roi = self.grab("storage_sell_btn")
        return {
            "master": bool(self.is_master_ui()),
            "sell_white": int(self.count(roi, "white")),
            "sell_white_need": int(self.t("sell_btn_white_px")),
            "sell_dark": round(float(self.count(roi, "dark") / float(max(1, roi.shape[0] * roi.shape[1]))), 3),
            "sell_dark_need": float(self.thr.get("sell_btn_dark_frac", 0.45)),
        }

    def is_dialog(self):
        """Hộp thoại 2 nút (Bán nhanh / Đổi mồi câu): nền tối + 2 pill trắng."""
        if self.dark_frac("dialog_title") < self.thr["dialog_dark_frac"]:
            return False
        return (self.count_roi("dialog_btn_left", "white") > self.t("dialog_btn_white_px")
                and self.count_roi("dialog_btn_right", "white") > self.t("dialog_btn_white_px"))

    def is_bait_dialog(self):
        """Hộp thoại đổi mồi: nền tối + có dấu hiệu badge/viền chọn ở dải ô mồi.

        Hộp thoại đổi mồi có cùng layout 2 nút với dialog chung, nhưng detector
        nút trắng có thể lệch theo ngôn ngữ/scale. Flow mồi chỉ cần biết dải ô
        mồi đã mở, nên nhận riêng bằng badge số lượng và viền chọn của 5 slot.
        """
        if self.is_result() or self.is_master_ui() or self.is_bait_shop():
            return False
        title_dark = self.dark_frac("dialog_title") >= self.thr["dialog_dark_frac"]
        badge_hits, selected_hits = self.bait_dialog_evidence()
        btn_floor = self.t("dialog_btn_white_px") * 0.05
        has_dialog_buttons = (self.count_roi("dialog_btn_left", "white") > btn_floor
                              and self.count_roi("dialog_btn_right", "white") > btn_floor)
        return selected_hits >= 1 or (title_dark and has_dialog_buttons and badge_hits >= 2)

    def bait_dialog_evidence(self):
        """Trả về (số badge có chữ số, số slot có viền chọn) ở hộp thoại mồi."""
        bd = self.cfg["bait_dialog"]
        badge_hits = 0
        selected_hits = 0
        for fx in bd["slot_centers_x"]:
            badge = self.grab_rect([fx - bd["badge_w"] / 2, bd["badge_y"],
                                    bd["badge_w"], bd["badge_h"]])
            glyph_px = self.count(badge, "white") + self.count(badge, "red_text")
            if glyph_px > max(6, self.t("badge_white_px") * 0.25):
                badge_hits += 1

            slot = self.grab_rect([fx - bd["slot_w"] / 2, bd["slot_top"],
                                   bd["slot_w"], bd["slot_h"]])
            if self._slot_selected(slot):
                selected_hits += 1
        return badge_hits, selected_hits

    def _slot_selected_score(self, slot):
        """Điểm viền hồng ô đang chọn; 0 nghĩa là không đủ tin cậy."""
        h, w = slot.shape[:2]
        m = max(4, int(6 * self.sx))
        pm = self.mask(slot, "pink_ui")
        edge_need = max(3, int(self.thr["slot_pink_px"] * self.sx / 12))
        edges = [pm[:m, :], pm[h - m:, :], pm[:, :m], pm[:, w - m:]]
        counts = [int(cv2.countNonZero(e)) for e in edges]
        strong = sum(c >= edge_need for c in counts)
        weak = sum(c >= edge_need * 0.45 for c in counts)
        if strong < 3 and not (strong >= 2 and weak >= 3):
            return 0.0
        return sum(min(c / float(edge_need), 2.0) for c in counts)

    def _slot_selected(self, slot):
        """Nhận diện viền hồng ô đang chọn, chịu được UI chỉ sáng một phần viền."""
        return self._slot_selected_score(slot) > 0.0

    def is_bait_shop(self):
        """Shop mồi câu (phím R): nhận bằng nút 'Mua' lớn + panel shop.

        Layout thật có thể làm vùng tiêu đề trên sáng/tối khác nhau theo hiệu ứng
        nền, nên không bắt buộc shop_panel_top phải tối. Nút Mua lớn ở đáy là tín
        hiệu chính; vùng Tiêu hao/panel dưới dùng làm xác nhận phụ để tránh nhầm
        với UI câu bình thường.
        """
        buy_white = self.count_roi("shop_buy_btn", "white")
        if buy_white < self.t("shop_buy_white_px"):
            return False
        if self.dark_frac("shop_panel_top") > self.thr["shop_panel_dark_frac"]:
            return True
        cost = self.grab("shop_cost")
        cost_white = self.count(cost, "white")
        cost_red = self.count(cost, "red_text")
        return (cost_white + cost_red) > self.t("shop_cost_red_px") * 3

    def bait_shop_debug(self):
        """Số đo live cho detector shop mồi, dùng khi flow R mở shop nhưng detect fail."""
        cost = self.grab("shop_cost")
        return {
            "buy_white": int(self.count_roi("shop_buy_btn", "white")),
            "buy_need": int(self.t("shop_buy_white_px")),
            "panel_dark": round(float(self.dark_frac("shop_panel_top")), 3),
            "panel_need": float(self.thr["shop_panel_dark_frac"]),
            "cost_white": int(self.count(cost, "white")),
            "cost_red": int(self.count(cost, "red_text")),
            "cost_need": int(self.t("shop_cost_red_px") * 3),
        }

    def shop_cost_insufficient(self):
        """Số 'Tiêu hao' trong shop chuyển ĐỎ khi tổng giá vượt số sò đang có."""
        return self.count_roi("shop_cost", "red_text") > self.t("shop_cost_red_px")

    def is_reward_popup(self):
        """Popup nhận vật phẩm sau khi mua mồi: panel trắng lớn giữa màn.

        Shop mồi cũng có nhiều panel trắng nằm trong ROI này; nếu không loại trừ
        trước thì recover_to_idle() sẽ tưởng shop là popup và click sai nút đóng.
        """
        if (self.is_bait_shop() or self.is_master_ui() or self.is_dialog()
                or self.is_sell_success_popup()):
            return False
        return self.count_roi("reward_popup", "white") > self.t("reward_popup_white_px")

    def is_sell_success_popup(self):
        """Popup 'Bán thành công' sau khi xác nhận bán nhanh."""
        if self.is_bait_shop() or self.is_dialog():
            return False
        return self.count_roi("sell_success_popup", "white") > self.t("sell_success_white_px")

    def _ocr_badge_count(self, fx):
        """OCR số lượng trên badge của ô mồi ở tâm fx. Trả về int >=0 hoặc None.

        Số mồi là chữ TRẮNG (còn) hoặc ĐỎ (0/hết). Crop badge, tách riêng
        chữ trắng + chữ đỏ thành ảnh nhị phân nét đậm trên nền tối rồi phóng to
        cho bộ nhận dạng đọc — RapidOCR đọc tốt nhất với chữ tương phản cao.
        """
        bd = self.cfg["bait_dialog"]
        # ROI badge hơi nới rộng để không cắt cụt chữ số đầu/cuối
        pad = bd.get("badge_pad_x", 0.004)
        badge = self.grab_rect([fx - bd["badge_w"] / 2 - pad, bd["badge_y"],
                                bd["badge_w"] + 2 * pad, bd["badge_h"]])
        if badge.size == 0:
            return None
        glyph = cv2.bitwise_or(self.mask(badge, "white"), self.mask(badge, "red_text"))
        if int(cv2.countNonZero(glyph)) < max(4, self.t("badge_white_px") * 0.25):
            return None  # gần như trống -> không có số để đọc
        # chữ trắng trên nền đen cho recognizer (đảo lại vì mask cho chữ = trắng)
        up = cv2.resize(glyph, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)
        rgb = cv2.cvtColor(up, cv2.COLOR_GRAY2BGR)
        return ocr.read_int(rgb)

    def bait_slots(self):
        """Đọc các ô mồi trong hộp thoại 'Đổi mồi câu', trái -> phải.

        Số lượng dưới mỗi ô: chữ TRẮNG = còn mồi, chữ ĐỎ (0) = hết.
        Ô đang chọn có viền hồng + dấu tích — đếm hồng ở vành ngoài để tránh
        nhầm với icon mồi màu hồng bên trong ô (ví dụ Mồi Câu Đa Năng).
        Trả về list dict: {index, x (tỉ lệ), has_stock, selected, count}.
          count: số mồi đọc được (int) hoặc None nếu OCR không ra số.
        """
        bd = self.cfg["bait_dialog"]
        out = []
        pending = []
        for i, fx in enumerate(bd["slot_centers_x"]):
            badge = self.grab_rect([fx - bd["badge_w"] / 2, bd["badge_y"],
                                    bd["badge_w"], bd["badge_h"]])
            white = self.count(badge, "white")
            red = self.count(badge, "red_text")
            # ô hết hàng hiện số 0 màu đỏ; ô còn hàng hiện số trắng
            has_stock = white > self.t("badge_white_px") and white > red * 1.5

            slot = self.grab_rect([fx - bd["slot_w"] / 2, bd["slot_top"],
                                   bd["slot_w"], bd["slot_h"]])
            # icon mồi bên trong có thể cũng màu hồng (vd Mồi Câu Đa Năng) nên
            # không đếm tổng: chỉ xét các dải viền ngoài, nhưng cho phép thiếu
            # một phần viền do scale/hiệu ứng hover làm màu hồng bị đứt đoạn.
            selected_score = self._slot_selected_score(slot)

            count = self._ocr_badge_count(fx)
            if count is not None:
                has_stock = count > 0  # số đọc được là nguồn tin cậy nhất
            elif red > max(6, self.t("badge_white_px") * 0.25) and red > white:
                count = 0  # số 0 đỏ rõ ràng mà OCR trượt -> coi như hết
            pending.append({"index": i, "x": fx, "has_stock": has_stock,
                            "selected_score": selected_score, "count": count})
        scores = [s["selected_score"] for s in pending]
        best_i = int(np.argmax(scores)) if scores else -1
        best = scores[best_i] if best_i >= 0 else 0.0
        second = max((s for j, s in enumerate(scores) if j != best_i), default=0.0)
        selected_i = None
        # Chỉ đánh dấu 1 ô selected nếu điểm tốt nhất nổi bật. Nếu 2 ô cùng
        # sáng viền/hover gần nhau, để None thay vì chọn nhầm ô đầu tiên.
        if best > 0.0 and (second <= 0.0 or best >= second * 1.35 or best - second >= 1.0):
            selected_i = best_i
        for i, item in enumerate(pending):
            out.append({"index": item["index"], "x": item["x"],
                        "has_stock": item["has_stock"],
                        "selected": i == selected_i, "count": item["count"]})
        return out

    def bait_strip_sig(self):
        """Ảnh xám thu nhỏ của cả dải ô mồi đang hiển thị — để so sánh trước/sau
        khi vuốt cuộn, biết danh sách đã hết (vuốt không làm đổi nội dung nữa)."""
        bd = self.cfg["bait_dialog"]
        cx = bd["slot_centers_x"]
        x0 = cx[0] - bd["slot_w"] / 2 - 0.008
        x1 = cx[-1] + bd["slot_w"] / 2 + 0.008
        img = self.grab_rect([x0, bd["slot_top"], x1 - x0, bd["slot_h"]])
        small = cv2.resize(img, (80, 20), interpolation=cv2.INTER_AREA)
        return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.int16)

    @staticmethod
    def strip_changed(a, b, thr=6.0):
        """True nếu 2 chữ ký dải ô khác nhau đáng kể (đã cuộn được)."""
        if a is None or b is None or a.shape != b.shape:
            return True
        return float(np.mean(np.abs(a - b))) >= thr
