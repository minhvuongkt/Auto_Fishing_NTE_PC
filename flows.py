# -*- coding: utf-8 -*-
"""Các chuỗi thao tác UI ngoài vòng lặp câu chính: vào chế độ câu, bán cá, đổi mồi.

Mỗi flow là chuỗi bước bấm phím/click có kiểm tra màn hình + timeout; hỏng ở
bước nào thì tự đóng UI quay về trạng thái câu để vòng lặp chính tiếp tục.
"""
import time


class Flows:
    def __init__(self, cfg, vision, inp, log, should_abort, human=None):
        self.cfg = cfg
        self.v = vision
        self.inp = inp
        self.log = log
        self.should_abort = should_abort  # callable -> True khi cần dừng (F8/F12/mất focus)
        self.human = human
        self.btn = cfg["buttons"]
        self._last_wait_aborted = False

    # ----- tiện ích -----
    def _wait(self, pred, timeout, poll=0.15):
        self._last_wait_aborted = False
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.should_abort():
                self._last_wait_aborted = True
                return False
            if pred():
                return True
            time.sleep(poll)
        return False

    def _click(self, name, settle=0.6):
        fx, fy = self.btn[name]
        self.inp.click_at(fx, fy, self.v)
        time.sleep(self.human.settle(settle) if self.human else settle)

    def _click_pos(self, pos, settle=0.6):
        fx, fy = pos
        self.inp.click_at(fx, fy, self.v)
        time.sleep(self.human.settle(settle) if self.human else settle)

    def _tap_key(self, key):
        self.inp.tap(key, self.cfg["timings"]["cast_hold"])

    def _wait_idle(self, timeout=2.0):
        """Đợi UI đóng hẳn về trạng thái câu trước khi mở flow kế tiếp."""
        if self.v.is_idle():
            return True
        return self._wait(self.v.is_idle, timeout, poll=0.1)

    # ----- 1. Vào chế độ câu (người dùng tự bấm F mở bảng, tool chỉ bấm nút) -----
    def start_from_prepare(self):
        self.log("Bảng chuẩn bị câu cá — bấm 'Bắt Đầu Câu Cá'...")
        self._click("prepare_start", settle=1.2)
        if not self._wait(self.v.is_idle, 8.0):
            self.log("[!] Chưa thấy trạng thái sẵn sàng câu sau khi bắt đầu.")
            return False
        self.log("Đã vào chế độ câu.")
        return True

    # ----- 2. Bán nhanh toàn bộ khoang cá -----
    def sell_fish(self):
        """Q -> tab Khoang cá -> BÁN NHANH -> Xác nhận -> popup thành công -> đóng cửa sổ."""
        self.log("$ Mở Chợ Cá để bán khoang cá (Q)...")
        self._tap_key(self.cfg["keys"]["open_shop"])
        if not self._wait(self.v.is_master_ui, 6.0):
            self.log("[!] Không mở được cửa sổ Chợ Cá.")
            self.recover_to_idle()
            return False
        self._click("master_tab_storage", settle=0.8)
        if not self._wait(self.v.is_storage_page, 5.0):
            dbg = getattr(self.v, "storage_debug", lambda: {})()
            self.log(f"[!] Không vào được tab khoang cá / chưa thấy BÁN NHANH. debug={dbg}")
            self.recover_to_idle()
            return False
        self._click("storage_quick_sell", settle=0.7)

        # Dialog bán nhanh đôi khi detector trượt do nền/scale. Không được gọi
        # recover_to_idle() ngay, vì recover sẽ bấm Hủy và làm mất giao dịch.
        saw_dialog = self._wait(self.v.is_dialog, 1.5, poll=0.15)
        if not saw_dialog:
            self.log("[~] Chưa detect được hộp thoại bán; vẫn thử bấm Xác nhận theo tọa độ.")

        sold = False
        for attempt in range(3):
            if self.should_abort():
                return False
            self._click("dialog_right", settle=0.55)  # Xác nhận
            if self._wait(self.v.is_sell_success_popup, 2.5, poll=0.15):
                sold = True
                self.log("$ Bán thành công — đóng popup kết quả.")
                fx, fy = self.cfg.get("click_close_pos", (0.135, 0.5))
                self.inp.click_at(fx, fy, self.v)
                time.sleep(self.human.settle(0.8) if self.human else 0.8)
                break
            if saw_dialog and not self.v.is_dialog():
                sold = True
                self.log("$ Dialog bán đã đóng sau Xác nhận; tiếp tục đóng UI.")
                break
            if not saw_dialog and not self.v.is_master_ui():
                sold = True
                self.log("$ UI bán đã đóng sau Xác nhận fallback.")
                break
            self.log(f"[~] Xác nhận bán chưa ăn, thử lại ({attempt + 2}/3)...")

        if not sold:
            self.log("[!] Chưa xác nhận được bán nhanh; giữ nguyên dialog/UI để tránh bấm Hủy nhầm.")
            return False
        self.recover_to_idle()
        return True

    def _log_slots(self, slots, page):
        stock_str = " ".join(
            f"#{s['index'] + 1}{'*' if s['selected'] else ''}:"
            + (str(s['count']) if s['count'] is not None
               else ('còn' if s['has_stock'] else 'hết'))
            for s in slots)
        self.log(f"Mồi (trang {page + 1}): {stock_str}")

    def _selected_or_single_counted(self, slots, allow_infer=True):
        selected = [s for s in slots if s["selected"]]
        if len(selected) == 1:
            return selected[0], False
        if len(selected) > 1:
            return None, False
        if not allow_infer:
            return None, False
        counted = [s for s in slots if s["count"] is not None]
        stocked = [s for s in slots if s["has_stock"]]
        if len(counted) == 1 and (counted[0]["has_stock"] or not stocked):
            return counted[0], True
        return None, False

    def _scroll_bait_strip(self):
        """Vuốt ngang dải ô mồi sang trái để lộ các ô bên phải.
        Trả về True nếu nội dung dải đổi (cuộn được), False nếu đã chạm cuối."""
        sc = self.cfg["bait_dialog"].get("scroll")
        if not sc:
            return False
        # Bỏ hover chuột khỏi dải ô trước/sau khi chụp; nếu không ảnh strip có
        # thể đổi chỉ vì hover, làm flow tưởng đã kéo sang trang mới.
        self.inp.move_to(0.5, 0.35, self.v)
        time.sleep(0.12)
        before = self.v.bait_strip_sig()

        bd = self.cfg["bait_dialog"]
        wide_from = min(0.95, sc["from_x"] + bd.get("slot_w", 0.0573))
        wide_to = max(0.05, sc["to_x"] - bd.get("slot_w", 0.0573))
        attempts = [
            (sc["from_x"], sc["to_x"], sc["y"], int(sc.get("steps", 18)), 0.12, 0.02),
            (wide_from, wide_to, sc["y"], max(26, int(sc.get("steps", 18)) + 8), 0.18, 0.026),
            (wide_from, wide_to, sc["y"] + 0.012, max(32, int(sc.get("steps", 18)) + 14), 0.22, 0.03),
        ]
        for fx0, fx1, fy, steps, hold, step_delay in attempts:
            self.inp.drag(fx0, fy, fx1, fy, self.v, steps=steps,
                          hold=hold, step_delay=step_delay)
            self.inp.move_to(0.5, 0.35, self.v)
            time.sleep(0.45)
            after = self.v.bait_strip_sig()
            if self.v.strip_changed(after, before):
                return True
        self.log("Vuốt dải mồi không đổi — có thể đã tới cuối hoặc game chưa nhận thao tác kéo.")
        return False

    # ----- 3. Đổi mồi khi nghi hết -----
    def switch_bait(self):
        """E -> quét HẾT các ô mồi (vuốt ngang qua từng trang) -> đổi sang ô đầu
        tiên còn hàng (từ trái). Trả về: 'switched' | 'bait_ok' | 'empty' | 'failed'."""
        self.log("? Nghi hết mồi — mở hộp thoại đổi mồi (E)...")
        if not self._wait_idle(2.0):
            self.recover_to_idle()
        self._tap_key(self.cfg["keys"]["change_bait"])
        if not self._wait(self.v.is_bait_dialog, 5.0):
            self.log("[!] Không mở được hộp thoại đổi mồi.")
            return "failed"
        time.sleep(0.3)

        sc = self.cfg["bait_dialog"].get("scroll", {})
        max_pages = max(1, int(sc.get("max_pages", 6)))
        cur_has_stock = None  # mồi đang chọn còn hàng không
        alt = None            # ô khác còn hàng để đổi sang
        saw_stock = False

        for page in range(max_pages):
            if self.should_abort():
                self._click("dialog_left", settle=0.6)
                return "failed"
            slots = self.v.bait_slots()
            self._log_slots(slots, page)
            if sum(1 for s in slots if s["selected"]) > 1:
                self.log("[!] Nhiều ô mồi cùng có viền chọn — bỏ qua viền để tránh chọn nhầm.")
            if any(s["has_stock"] for s in slots):
                saw_stock = True
            sel, _ = self._selected_or_single_counted(slots, allow_infer=False)
            if sel is not None:
                cur_has_stock = sel["has_stock"]
                if cur_has_stock:
                    break  # mồi đang dùng vẫn còn -> bait_ok, khỏi vuốt quét
            if cur_has_stock is False:
                # Chỉ chọn mồi khác khi đã biết chắc ô hiện tại đã hết; nếu chưa
                # detect được selected thì not selected có thể là chính ô đang dùng.
                alt = next((s for s in slots if s["has_stock"]
                            and (sel is None or s["index"] != sel["index"])), None)
                if alt is not None:
                    break
            # chưa thấy ô còn hàng -> vuốt sang trang kế; hết cuộn thì dừng
            if page < max_pages - 1:
                if not self._scroll_bait_strip():
                    self.log("Đã xem hết các ô mồi (không cuộn thêm được).")
                    break

        # mồi đang dùng vẫn còn (đọc ở trang đầu) -> không cần đổi
        if cur_has_stock:
            self._click("dialog_left", settle=0.6)  # Hủy
            self._wait_idle(2.0)
            return "bait_ok"
        if alt is None:
            self._click("dialog_left", settle=0.6)  # Hủy — không còn loại nào
            self._wait_idle(2.0)
            if saw_stock and cur_has_stock is None:
                self.log("[!] Có mồi còn hàng nhưng không nhận ra ô đang chọn — không tự đổi để tránh chọn nhầm.")
                return "failed"
            return "empty"
        self.inp.click_at(alt["x"], self.cfg["bait_dialog"]["click_y"], self.v)
        time.sleep(0.5)
        self._click("dialog_right", settle=1.2)  # Thay đổi
        self._wait_idle(3.0)
        self.log(f"Đã đổi sang ô mồi #{alt['index'] + 1} (còn {alt['count']}).")
        return "switched"

    # ----- 4. Kiểm tra nhanh số mồi của ô đang chọn -----
    def check_bait_level(self):
        """Mở hộp thoại đổi mồi (E) chỉ để XEM rồi Hủy — không đổi gì.

        Trả về (has_stock, count) của ô mồi đang chọn; count là SỐ MỒI thật đọc
        được bằng OCR (hoặc None nếu OCR không ra số). Trả "ambiguous_stock"
        hoặc "ambiguous_empty" nếu mở được hộp thoại và đọc được slot nhưng
        không xác định được ô đang chọn; None nếu không mở/đọc được hộp thoại.
        """
        self.log("Kiểm tra số mồi còn lại (mở hộp thoại E)...")
        self._tap_key(self.cfg["keys"]["change_bait"])
        if not self._wait(self.v.is_bait_dialog, 5.0):
            if self._last_wait_aborted:
                self.log("[!] Dừng kiểm tra mồi do tạm dừng/mất focus.")
            else:
                self.log("[!] Không mở được hộp thoại đổi mồi để kiểm tra.")
            return None
        time.sleep(0.3)
        sc = self.cfg["bait_dialog"].get("scroll", {})
        max_pages = max(1, int(sc.get("max_pages", 6)))
        cur = None
        saw_slot_data = False
        any_stock = False
        for page in range(max_pages):
            slots = self.v.bait_slots()
            self._log_slots(slots, page)
            if sum(1 for s in slots if s["selected"]) > 1:
                self.log("[!] Nhiều ô mồi cùng có viền chọn — không lấy ô đầu tiên làm ô đang dùng.")
            if any(s["has_stock"] or s["count"] is not None for s in slots):
                saw_slot_data = True
            if any(s["has_stock"] for s in slots):
                any_stock = True
            cur, inferred = self._selected_or_single_counted(slots)
            if cur is not None:
                if inferred:
                    self.log(f"Không thấy viền chọn — dùng ô #{cur['index'] + 1} "
                             f"vì OCR đọc duy nhất {cur['count']}.")
                break
            if page < max_pages - 1:
                if not self._scroll_bait_strip():
                    self.log("Đã xem hết các ô mồi nhưng chưa xác định được ô đang chọn.")
                    break
        self._click("dialog_left", settle=0.6)  # Hủy — chỉ xem
        self._wait_idle(2.0)
        if cur is None:
            if saw_slot_data:
                self.log("[!] Đã mở và đọc được hộp thoại mồi nhưng chưa nhận ra ô đang chọn.")
                return "ambiguous_stock" if any_stock else "ambiguous_empty"
            self.log("[!] Đã mở hộp thoại mồi nhưng không đọc được dữ liệu ô mồi.")
            return None
        return cur["has_stock"], cur["count"]

    # ----- 5. Mua mồi ở shop (phím R) -----
    def buy_bait(self, amount):
        """R -> chọn ô mồi cấu hình -> bấm + tới số lượng -> Mua -> đóng shop.

        Số lượng mặc định của shop là 1, mỗi cú + thêm 1. Nếu tổng giá vượt số
        sò đang có (số 'Tiêu hao' chuyển đỏ) thì bấm - giảm dần; không đủ sò
        mua nổi 1 mồi thì bỏ. Trả về số mồi đã mua (0 = thất bại).
        """
        bs = self.cfg["bait_shop"]
        ab = self.cfg["flows"].get("auto_buy_bait", {})
        amount = max(1, min(int(amount), 99))
        self.log(f"$ Mở shop mồi câu (R) — dự định mua {amount} mồi...")
        if not self.v.is_bait_shop():
            if not self._wait_idle(2.0):
                self.recover_to_idle()
            self._tap_key(self.cfg["keys"]["open_bait_shop"])
            if not self._wait(self.v.is_bait_shop, 6.0):
                dbg = getattr(self.v, "bait_shop_debug", lambda: {})()
                self.log(f"[!] Detector chưa nhận shop mồi sau R — vẫn thử mua theo tọa độ. debug={dbg}")
                time.sleep(0.8)
        time.sleep(self.human.settle(0.5) if self.human else 0.5)

        # chọn ô mồi: đếm từ 1, trái -> phải rồi xuống hàng, mỗi hàng grid_cols ô
        idx = max(1, int(ab.get("shop_item_index", 1))) - 1
        cols = max(1, int(bs.get("grid_cols", 3)))
        visible = cols * max(1, int(bs.get("grid_rows_visible", 3)))
        if idx >= visible:
            self.log(f"[!] shop_item_index={idx + 1} vượt quá {visible} ô nhìn thấy được — dùng ô #1.")
            idx = 0
        row, col = divmod(idx, cols)
        ox, oy = bs["grid_origin"]
        self.inp.click_at(ox + col * bs["grid_dx"], oy + row * bs["grid_dy"], self.v)
        time.sleep(self.human.settle(0.7) if self.human else 0.7)
        if self.should_abort():
            return 0

        if amount > 1:
            px, py = bs["plus_btn"]
            self.inp.multi_click(px, py, self.v, amount - 1)
            time.sleep(0.3)
        # thiếu sò: giảm dần tới khi giá hết đỏ
        reduced = 0
        while amount > 1 and self.v.shop_cost_insufficient():
            if self.should_abort():
                return 0
            self.inp.multi_click(*bs["minus_btn"], self.v, 1)
            amount -= 1
            reduced += 1
            time.sleep(0.12)
        if reduced:
            self.log(f"Không đủ sò cho cả mẻ — giảm còn {amount} mồi.")
        if self.v.shop_cost_insufficient():
            self.log("[!] Không đủ sò để mua dù chỉ 1 mồi — bỏ qua, đóng shop.")
            self.recover_to_idle()
            return 0

        purchased = False
        self._click_pos(bs["buy_btn"], settle=0.8)
        if self._wait(self.v.is_reward_popup, 4.0, poll=0.2):
            self.log("$ Thấy popup nhận vật phẩm — đóng popup mua mồi.")
            purchased = True
            self._click_pos(bs.get("reward_close", (0.5, 0.86)), settle=0.8)
        elif self._wait(self.v.is_dialog, 0.8, poll=0.2):
            self._click("dialog_right", settle=1.0)  # xác nhận nếu game hỏi lại
            if self._wait(self.v.is_reward_popup, 3.0, poll=0.2):
                purchased = True
                self._click_pos(bs.get("reward_close", (0.5, 0.86)), settle=0.8)
        else:
            self.log("[!] Bấm Mua nhưng chưa thấy popup nhận vật phẩm/xác nhận — coi như chưa mua.")
        self.recover_to_idle()
        if not purchased:
            return 0
        self.log(f"$ Đã mua {amount} mồi.")
        return amount

    # ----- khôi phục -----
    def recover_to_idle(self):
        """Đóng mọi UI đang mở rồi chờ idle: hộp thoại -> Hủy, shop mồi/Chợ Cá -> X."""
        if self.should_abort():
            return False
        for _ in range(4):
            if self.should_abort():
                return False
            if self.v.is_sell_success_popup():
                fx, fy = self.cfg.get("click_close_pos", (0.135, 0.5))
                self.inp.click_at(fx, fy, self.v)
                time.sleep(self.human.settle(0.7) if self.human else 0.7)
            elif self.v.is_reward_popup():
                self._click_pos(self.cfg["bait_shop"].get("reward_close", (0.5, 0.86)), settle=0.8)
            elif self.v.is_dialog() or self.v.is_bait_dialog():
                self._click("dialog_left", settle=0.6)
            elif self.v.is_bait_shop():
                self._click_pos(self.cfg["bait_shop"]["close_btn"], settle=0.9)
            elif self.v.is_master_ui():
                self._click("master_close", settle=0.9)
            elif self.v.is_idle():
                return True
            else:
                break
        ok = self._wait(self.v.is_idle, 6.0)
        if not ok:
            self.log("[!] Chưa quay lại được trạng thái câu — tiếp tục quan sát.")
        return ok
