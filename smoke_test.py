# -*- coding: utf-8 -*-
"""Kiểm thử khô: khởi tạo mọi module với config thật, KHÔNG gửi phím/chuột."""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
cfg = json.load(open(cfg_path, encoding="utf-8"))

from humanizer import Humanizer
from vision import Vision
from controller import InputController
from fight import FightController
from flows import Flows

h = Humanizer(cfg)
v = Vision(cfg)
inp = InputController(cfg, h)
f = FightController(cfg, v, inp, h)
fl = Flows(cfg, v, inp, print, lambda: True, h)  # should_abort=True -> không bao giờ click
print(f"Vision: {v.W}x{v.H}, sx={v.sx:.2f}, area={v.area_scale:.2f}")

# humanizer: phân phối hợp lệ
rs = [h.reaction() for _ in range(2000)]
assert all(0.1 < r < 3.0 for r in rs), "reaction ngoài khoảng"
print(f"reaction: min={min(rs)*1000:.0f}ms max={max(rs)*1000:.0f}ms avg={sum(rs)/len(rs)*1000:.0f}ms")
holds = [h.hold(0.08) for _ in range(1000)]
assert all(0.03 <= x < 0.2 for x in holds), "hold ngoài khoảng"
gaps = [h.gap(2.5) for _ in range(1000)]
print(f"hold(0.08): {min(holds):.3f}-{max(holds):.3f}; gap(2.5): {min(gaps):.2f}-{max(gaps):.2f}")
mh = [h.fight_min_hold(0.13) for _ in range(1000)]
assert all(0.05 <= x <= 0.13 * 1.3 for x in mh)
path = h.mouse_path(100, 100, 900, 600)
assert path[-1][:2] == (900, 600), f"mouse_path không kết thúc tại đích: {path[-1]}"
assert 5 <= len(path) <= 30, f"số bước lạ: {len(path)}"
print(f"mouse_path: {len(path)} bước, kết thúc đúng đích")
brs = [h.microbreak() for _ in range(5000)]
nb = sum(1 for b in brs if b > 0)
print(f"microbreak: {nb/len(brs)*100:.1f}% số lần roll có nghỉ (kỳ vọng ~7.5%)")
limit = "không giới hạn" if h.session_limit is None else f"{h.session_limit/60:.0f} phút"
print(f"session limit: {limit}")

# vision: các detector mới chạy không lỗi trên màn hình hiện tại (desktop)
for name in ["is_bite", "is_fighting", "is_idle", "is_result", "is_world_prompt",
             "is_prepare_panel", "is_master_ui", "is_storage_page", "is_dialog",
             "is_bait_dialog", "is_bait_shop", "is_reward_popup", "is_sell_success_popup",
             "shop_cost_insufficient"]:
    r = getattr(v, name)()
    assert r in (True, False), name
    print(f"{name}: {r}")
green, marker, w = v.fight_bar()
print(f"fight_bar: green={green} marker={marker} w={w}")
slots = v.bait_slots()
assert len(slots) == 5
assert all("count" in s for s in slots), "bait_slots thiếu trường count"
assert all(s["count"] is None or isinstance(s["count"], int) for s in slots)
print("bait_slots:", [(s['has_stock'], s['selected'], s['count']) for s in slots])
badge_hits, selected_hits = v.bait_dialog_evidence()
assert isinstance(badge_hits, int) and isinstance(selected_hits, int)
print(f"bait_dialog_evidence: badges={badge_hits} selected={selected_hits}")

# vuốt quét ô mồi: chữ ký dải + so sánh
sig = v.bait_strip_sig()
assert sig.shape == (20, 80), f"bait_strip_sig shape lạ: {sig.shape}"
assert v.strip_changed(sig, None) is True  # khác None -> coi như đã đổi
assert v.strip_changed(sig, sig.copy(), thr=3.0) is False  # giống hệt -> chưa đổi
assert hasattr(inp, "drag"), "controller thiếu drag()"
sc = cfg["bait_dialog"]["scroll"]
for k in ["from_x", "to_x", "y", "steps", "max_pages"]:
    assert k in sc, f"thiếu bait_dialog.scroll.{k}"
print("bait scroll cfg OK:", sc)

# ocr: module nạp được, read_int trả int trên ảnh số tổng hợp (hoặc None nếu chưa cài rapidocr)
import ocr as _ocr
import numpy as _np, cv2 as _cv2
_img = _np.zeros((40, 90, 3), dtype=_np.uint8)
_cv2.putText(_img, "42", (8, 30), _cv2.FONT_HERSHEY_DUPLEX, 1.0, (255, 255, 255), 2)
_img = _cv2.resize(_img, None, fx=4, fy=4, interpolation=_cv2.INTER_CUBIC)
if _ocr.available():
    _r = _ocr.read_int(_img)
    assert _r is None or isinstance(_r, int), "read_int trả kiểu lạ"
    print(f"ocr: available, read_int(mẫu '42') = {_r}")
else:
    print("ocr: CHƯA cài rapidocr-onnxruntime — bot sẽ lùi về cơ chế phản ứng khi hết sạch mồi")

# flows: should_abort=True nên _wait phải thoát ngay không click
assert fl._wait(lambda: False, 0.5) is False
print("flows._wait abort OK")

# config: mọi key code dùng đều tồn tại
for k in ["world_fkey", "world_prompt", "prepare_button", "prepare_top", "master_header",
          "storage_sell_btn", "dialog_btn_left", "dialog_btn_right", "dialog_title",
          "shop_buy_btn", "shop_panel_top", "shop_cost", "sell_success_popup"]:
    assert k in cfg["rois"], f"thiếu roi {k}"
for k in ["prepare_start", "master_tab_storage", "storage_quick_sell",
          "dialog_left", "dialog_right", "master_close"]:
    assert k in cfg["buttons"], f"thiếu button {k}"
bs = cfg["bait_shop"]
for k in ["grid_origin", "grid_dx", "grid_dy", "grid_cols", "grid_rows_visible",
          "minus_btn", "plus_btn", "buy_btn", "close_btn"]:
    assert k in bs, f"thiếu bait_shop.{k}"
ab = cfg["flows"]["auto_buy_bait"]
for k in ["enabled", "shop_item_index", "buy_amount", "assume_stock"]:
    assert k in ab, f"thiếu auto_buy_bait.{k}"
assert cfg["keys"].get("open_bait_shop"), "thiếu keys.open_bait_shop"
print("\nSMOKE TEST OK — mọi module khởi tạo và chạy đúng.")
