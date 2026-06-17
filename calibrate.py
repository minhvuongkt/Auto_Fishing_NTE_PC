# -*- coding: utf-8 -*-
"""Công cụ căn chỉnh: kiểm tra ROI và ngưỡng màu trên máy của bạn.

  python calibrate.py shot   -> chụp màn hình, vẽ khung ROI, lưu calib_rois.png
  python calibrate.py probe  -> in liên tục kết quả nhận diện (Ctrl+C để dừng)
  python calibrate.py bait   -> (mở hộp thoại E trước) lưu badge từng ô mồi + số OCR

Cách dùng: vào game, mở từng màn hình (đứng chờ / cá cắn / đang kéo / kết quả)
rồi chạy "probe" để xem bot có nhận đúng trạng thái không; chạy "shot" ở màn
kéo cá để kiểm tra khung ROI có trùm đúng thanh kéo + 2 icon tròn hay không.
"""
import ctypes
import json
import os
import sys
import time

import cv2
import numpy as np

from vision import Vision, _new_mss
from controller import InputController


def load_cfg():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def shot(cfg):
    v = Vision(cfg)
    with _new_mss() as sct:
        mon = sct.monitors[1]
        img = cv2.cvtColor(np.asarray(sct.grab(mon)), cv2.COLOR_BGRA2BGR)
    for name in cfg["rois"]:
        x, y, w, h = v.roi_px(name)
        x, y = x - v.mon_left, y - v.mon_top
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 2)
        cv2.putText(img, name, (x, max(15, y - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
    fx, fy = cfg["click_close_pos"]
    cx, cy = int(fx * v.W), int(fy * v.H)
    cv2.drawMarker(img, (cx, cy), (255, 0, 255), cv2.MARKER_CROSS, 30, 3)
    for name, (bx, by) in cfg.get("buttons", {}).items():
        px, py = int(bx * v.W), int(by * v.H)
        cv2.drawMarker(img, (px, py), (0, 255, 255), cv2.MARKER_CROSS, 24, 2)
        cv2.putText(img, name, (px + 14, py + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
    bd = cfg.get("bait_dialog")
    if bd:
        for i, sx_ in enumerate(bd["slot_centers_x"]):
            px, py = int(sx_ * v.W), int(bd["click_y"] * v.H)
            cv2.drawMarker(img, (px, py), (255, 255, 0), cv2.MARKER_CROSS, 18, 2)
            cv2.putText(img, f"moi{i + 1}", (px - 18, py - 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
    bs = cfg.get("bait_shop")
    if bs:
        ox, oy = bs["grid_origin"]
        cols, rows = bs.get("grid_cols", 3), bs.get("grid_rows_visible", 3)
        for i in range(cols * rows):
            r, c = divmod(i, cols)
            px = int((ox + c * bs["grid_dx"]) * v.W)
            py = int((oy + r * bs["grid_dy"]) * v.H)
            cv2.drawMarker(img, (px, py), (0, 165, 255), cv2.MARKER_CROSS, 18, 2)
            cv2.putText(img, f"shop{i + 1}", (px - 22, py - 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 165, 255), 1)
        for name in ("minus_btn", "plus_btn", "buy_btn", "close_btn"):
            px, py = int(bs[name][0] * v.W), int(bs[name][1] * v.H)
            cv2.drawMarker(img, (px, py), (0, 165, 255), cv2.MARKER_TILTED_CROSS, 20, 2)
            cv2.putText(img, name, (px + 12, py + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 165, 255), 1)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calib_rois.png")
    cv2.imwrite(out, img)
    print(f"Đã lưu {out} — mở lên so với UI trong game để chỉnh 'rois' trong config.json.")


def probe(cfg):
    v = Vision(cfg)
    inp = InputController(cfg)
    print("In trạng thái mỗi 0.5s — vào game và thử từng màn hình (Ctrl+C để dừng).")
    while True:
        idle = v.count(v.grab("idle_e_icon"), "white")
        bite = v.count(v.grab("bite_f_ring"), "bite_blue")
        gold = v.count(v.grab("fight_left_icon"), "gold_ring")
        cyan = v.count(v.grab("fight_right_icon"), "cyan_ring")
        white = v.count(v.grab("result_circle"), "white")
        cap = v.grab("result_capsule")
        dark_frac = v.count(cap, "dark") / (cap.shape[0] * cap.shape[1])
        prep_white = v.count(v.grab("prepare_button"), "white")
        ptop = v.grab("prepare_top")
        prep_dark = v.count(ptop, "dark") / (ptop.shape[0] * ptop.shape[1])
        green, marker, _ = v.fight_bar()
        states = []
        if v.is_fighting():
            states.append("FIGHT")
        if v.is_bite():
            states.append("BITE")
        if v.is_result():
            states.append("RESULT")
        if v.is_idle():
            states.append("IDLE")
        ui = []
        if v.is_world_prompt():
            ui.append("WORLD")
        if v.is_prepare_panel():
            ui.append("PREP")
        if v.is_storage_page():
            ui.append("KHOANG")
        elif v.is_master_ui():
            ui.append("SHOP")
        if v.is_bait_shop():
            ui.append("BAITSHOP" + ("(đỏ)" if v.shop_cost_insufficient() else ""))
        dialog = v.is_dialog()
        bait_dialog = v.is_bait_dialog()
        if dialog:
            ui.append("DIALOG")
        if bait_dialog:
            ui.append("BAITDIALOG")
        extra = f" ui={'+'.join(ui)}" if ui else ""
        if bait_dialog:
            slots = v.bait_slots()
            badge_hits, selected_hits = v.bait_dialog_evidence()
            extra += " moi=" + ",".join(
                ("[" if s["selected"] else "")
                + (str(s["count"]) if s["count"] is not None
                   else ("còn" if s["has_stock"] else "hết"))
                + ("]" if s["selected"] else "") for s in slots)
            extra += f" evidence={badge_hits}/{selected_hits}"
        print(f"[{time.strftime('%H:%M:%S')}] state={'+'.join(states) or 'UNKNOWN':<8} "
              f"idle_white={idle:5d}/{v.t('idle_white_px'):.0f} "
              f"bite_blue={bite:5d}/{v.t('bite_blue_px'):.0f} "
              f"gold={gold:4d} cyan={cyan:4d} (nguong {v.t('fight_ring_px'):.0f}) "
              f"result_white={white:6d}/{v.t('result_white_px'):.0f} "
              f"dark={dark_frac:.2f}/{v.thr['capsule_dark_frac']:.2f} "
              f"prep_white={prep_white:5d}/{v.t('prepare_white_px'):.0f} "
              f"prep_dark={prep_dark:.2f}/{v.thr['prepare_dark_frac']:.2f} "
              f"green={green} marker={None if marker is None else round(marker, 1)} "
              f"fg='{inp.foreground_title()}'{extra}")
        time.sleep(0.5)


def bait(cfg):
    """Mở hộp thoại đổi mồi (E) trong game rồi chạy lệnh này: lưu ảnh từng badge
    số lượng + in số OCR đọc được, để kiểm tra/căn `bait_dialog.badge_*`.

      python calibrate.py bait  -> calib_bait_slotN.png + in count từng ô
    """
    import cv2
    v = Vision(cfg)
    bd = cfg["bait_dialog"]
    pad = bd.get("badge_pad_x", 0.004)
    if not v.is_bait_dialog():
        print("[!] Chưa thấy hộp thoại 'Đổi mồi câu' — mở bằng phím E trong game rồi chạy lại.")
    badge_hits, selected_hits = v.bait_dialog_evidence()
    print(f"bait_dialog={v.is_bait_dialog()} evidence_badges={badge_hits} evidence_selected={selected_hits}")
    slots = v.bait_slots()
    here = os.path.dirname(os.path.abspath(__file__))
    for s in slots:
        fx = s["x"]
        badge = v.grab_rect([fx - bd["badge_w"] / 2 - pad, bd["badge_y"],
                             bd["badge_w"] + 2 * pad, bd["badge_h"]])
        up = cv2.resize(badge, None, fx=6, fy=6, interpolation=cv2.INTER_NEAREST)
        out = os.path.join(here, f"calib_bait_slot{s['index'] + 1}.png")
        cv2.imwrite(out, up)
        mark = "*" if s["selected"] else " "
        print(f"  ô#{s['index'] + 1}{mark} count={s['count']} has_stock={s['has_stock']} -> {out}")
    print("Mở các file calib_bait_slot*.png xem badge có trùm đúng con số không; "
          "lệch thì chỉnh bait_dialog.badge_y / badge_h / badge_pad_x trong config.json.")


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    cfg = load_cfg()
    mode = sys.argv[1] if len(sys.argv) > 1 else "shot"
    if mode == "probe":
        probe(cfg)
    elif mode == "bait":
        bait(cfg)
    else:
        shot(cfg)


if __name__ == "__main__":
    main()
