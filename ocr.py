# -*- coding: utf-8 -*-
"""Đọc CHỮ SỐ (số lượng mồi) bằng RapidOCR — recognition-only, nạp lười.

RapidOCR (ONNX, model PaddleOCR đi kèm) chạy offline, đa ngôn ngữ. Badge số mồi
nằm ở vị trí cố định nên ta gọi thẳng bộ nhận dạng (bỏ detection) cho nhanh
(~20ms/crop) và ổn định. Engine nạp ở lần đọc đầu tiên để không làm chậm lúc bot
khởi động; nếu không cài được rapidocr thì mọi hàm trả None và bot tự lùi về cơ
chế phản ứng khi hết sạch mồi.
"""
import logging
import re

# RapidOCR/onnxruntime hay in log model lúc khởi tạo — hạ mức để khỏi rác console.
for _name in ("rapidocr_onnxruntime", "RapidOCR", "onnxruntime"):
    logging.getLogger(_name).setLevel(logging.ERROR)

_engine = None
_tried = False


def _get():
    """Trả về engine RapidOCR (singleton) hoặc None nếu không nạp được."""
    global _engine, _tried
    if _engine is not None or _tried:
        return _engine
    _tried = True
    try:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    except Exception:
        _engine = None
    return _engine


def available():
    """True nếu OCR dùng được (đã nạp engine thành công)."""
    return _get() is not None


# nhầm lẫn chữ↔số thường gặp khi OCR badge số nhỏ + chuẩn hóa số full-width
_FIX = str.maketrans({
    "〇": "0", "Ｏ": "0", "O": "0", "o": "0", "Q": "0", "D": "0",
    "ｌ": "1", "l": "1", "I": "1", "i": "1", "|": "1", "！": "1",
    "Ｂ": "8", "S": "5", "s": "5", "B": "8",
    "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
    "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
})


def read_int(img):
    """Đọc một số nguyên không âm từ ảnh đã crop+phóng to. None nếu không ra số.

    Bỏ tiền tố 'x'/'×' (badge số lượng) và mọi ký tự không phải chữ số, lấy cụm
    chữ số đầu tiên.
    """
    eng = _get()
    if eng is None:
        return None
    try:
        res, _ = eng(img, use_det=False, use_cls=False, use_rec=True)
    except Exception:
        return None
    if not res:
        return None
    text = "".join(item[0] for item in res).translate(_FIX)
    m = re.search(r"\d+", text)
    if not m:
        return None
    try:
        return int(m.group())
    except ValueError:
        return None
