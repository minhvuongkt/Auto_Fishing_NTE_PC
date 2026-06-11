# -*- coding: utf-8 -*-
"""Công cụ căn chỉnh: kiểm tra ROI và ngưỡng màu trên máy của bạn.

  python calibrate.py shot   -> chụp màn hình, vẽ khung ROI, lưu calib_rois.png
  python calibrate.py probe  -> in liên tục kết quả nhận diện (Ctrl+C để dừng)

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
        print(f"[{time.strftime('%H:%M:%S')}] state={'+'.join(states) or 'UNKNOWN':<8} "
              f"idle_white={idle:5d}/{v.t('idle_white_px'):.0f} "
              f"bite_blue={bite:5d}/{v.t('bite_blue_px'):.0f} "
              f"gold={gold:4d} cyan={cyan:4d} (nguong {v.t('fight_ring_px'):.0f}) "
              f"result_white={white:6d}/{v.t('result_white_px'):.0f} "
              f"dark={dark_frac:.2f}/{v.thr['capsule_dark_frac']:.2f} "
              f"green={green} marker={None if marker is None else round(marker, 1)} "
              f"fg='{inp.foreground_title()}'")
        time.sleep(0.5)


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
    else:
        shot(cfg)


if __name__ == "__main__":
    main()
