# NTE Auto Fishing — Tài liệu kỹ thuật (dành cho người sửa code)

> 📖 Nếu bạn chỉ muốn **sử dụng** tool, đọc [README.md](README.md) — hướng dẫn
> người dùng đầy đủ. File này dành cho người muốn hiểu/chỉnh source code.

Bot đọc màn hình (OpenCV + mss) và giả lập phím (SendInput scancode qua
PyDirectInput) để chạy trọn chu trình câu cá: **thả cần → chờ cá cắn → giật cần
→ minigame kéo cá A/D → đóng màn kết quả → lặp lại**. Không đọc bộ nhớ game,
không inject DLL.

## ⚠️ Cảnh báo trước khi dùng

- NTE cấm macro/tool thứ ba trong điều khoản dịch vụ; game dùng anti-cheat
  kernel **ACE** (driver `HtAntiCheatDriver`). ACE không chặn SendInput về mặt
  kỹ thuật, nhưng **rủi ro khóa tài khoản luôn tồn tại** — dùng phiên ngắn,
  đừng treo máy 24/7. Bạn tự chịu trách nhiệm khi sử dụng.
- Mồi câu bị trừ mỗi lần thả cần; bot theo dõi "sổ mồi" nội bộ (`assume_stock`
  trừ dần theo lần thả, cộng khi mua) và tự mua thêm ở shop (R) khi ước tính
  không đủ cho chu kỳ câu-bán. Chỉ khi mua thất bại (hết sò...) mới dừng + *beep*.

## Yêu cầu

| Mục | Yêu cầu |
|---|---|
| Hệ điều hành | Windows 10/11, game ở **màn hình chính** |
| Python | 3.11+ |
| Chế độ hiển thị | **Borderless / Windowed Fullscreen** (fullscreen exclusive có thể chụp ra màn đen) |
| Độ phân giải | 1920×1080 khuyến nghị (độ phân giải khác tự co giãn theo tỉ lệ, nên kiểm tra bằng `calibrate.py`) |
| Đồ họa | **TẮT DLSS/FSR + frame generation, TẮT HDR/màu lọc** — các filter này làm sai màu pixel, bot không nhận diện được |
| Quyền | Chạy PowerShell **Run as Administrator** (game + ACE chạy elevated, không có admin thì phím giả lập bị Windows chặn im lặng) |
| Trong game | Thời gian ban ngày ổn nhất; **tránh hoàng hôn/bình minh** (ánh vàng làm hỏng nhận diện vạch vàng) |

## Cài đặt

```powershell
pip install -r requirements.txt
```

## Chạy

Cách 1 — **run.bat** (khuyên dùng): double-click `run.bat`, file tự xin quyền
Administrator rồi chạy `python main.py`.

Cách 2 — **file exe**: chạy `dist\NTE-AutoFishing.exe` (đã nhúng manifest UAC,
tự hiện hộp thoại xin quyền admin). File `config.json` phải nằm **cùng thư mục**
với exe. Lưu ý: exe đóng gói bằng PyInstaller có thể bị antivirus báo nhầm —
nếu bị chặn thì thêm ngoại lệ hoặc dùng cách 1.

Cách 3 — thủ công: mở PowerShell **Run as Administrator** tại thư mục tool:

```powershell
python main.py
```

Muốn tự build lại exe:

```powershell
pip install pyinstaller
python -m PyInstaller --noconfirm --onefile --uac-admin --name NTE-AutoFishing main.py
Copy-Item config.json dist\
```

Sau khi chạy: vào game, đến điểm câu (thấy nút **F** móc câu), bấm **F8** để
bắt đầu. Bot khởi động ở trạng thái tạm dừng.

| Phím | Tác dụng |
|---|---|
| **F8** | Chạy / tạm dừng (kèm tiếng beep) |
| **F12** | Thoát, in thống kê phiên |

Bot chỉ bơm phím khi cửa sổ game đang focus (`window_titles` trong config) — alt-tab ra ngoài là bot tự ngừng bấm.

## Cách hoạt động

```
IDLE (icon E hiện)        --F-->  chờ cá cắn
chờ cá cắn (≤90s)         --vòng xanh quanh nút F-->  bấm F giật cần
giật cần                  --2 icon tròn trên đầu màn hình-->  FIGHT
FIGHT: giữ vạch vàng trong vùng xanh bằng A/D
       (vùng xanh = vị trí cá, "Sức chịu đựng của cá" giảm khi trùng nhau,
        "Dây câu" là giới hạn thời gian — hết là sẩy cá)
thanh biến mất            -->  chờ màn kết quả -> click vùng trống -> IDLE
```

Nhận diện hoàn toàn bằng đếm pixel theo dải màu HSV trong các ô ROI nhỏ:

- **Cá cắn:** vòng sáng xanh dương quanh nút F (H 100–130).
- **Đang kéo:** icon viền vàng (trái) + icon viền cyan (phải) trên đầu màn hình.
- **Thanh kéo:** vùng xanh lá (H 65–95) và vạch vàng (H 18–45, V cao) trong dải ROI ngang.
- **Kết quả:** vòng tròn trắng lớn giữa màn hình + khung "Cấp Câu Cá" tối phía trên.

Điều khiển A/D dạng bám-đuổi có bù quán tính: sai số = tâm vùng xanh − vạch vàng,
cộng dự đoán chuyển động vùng xanh, trừ "phanh" theo vận tốc vạch vàng; dead zone
kèm hysteresis và thời gian giữ phím tối thiểu 0.13s (UE5 bỏ qua phím quá ngắn).

## Căn chỉnh khi nhận diện sai

```powershell
python calibrate.py shot    # chụp màn hình + vẽ khung ROI -> calib_rois.png
python calibrate.py probe   # in trực tiếp trạng thái nhận diện mỗi 0.5s
```

Mở từng màn hình trong game (đứng chờ / cá cắn / đang kéo / kết quả) rồi xem
`probe` có in đúng `IDLE / BITE / FIGHT / RESULT` không. Chỉnh `config.json`:

| Khóa | Ý nghĩa |
|---|---|
| `rois.*` | Vị trí các ô nhận diện, theo tỉ lệ `[x, y, w, h]` chia cho 1920×1080 |
| `hsv.*` | Dải màu `[H, S, V]` thấp–cao (OpenCV: H 0–179) |
| `thresholds.*_px` (bite/idle/ring/result) | Ngưỡng **đếm pixel**, tự co giãn theo diện tích màn hình so với 1080p |
| `thresholds.*_frac` (green_col/capsule_dark) | **Tỉ lệ 0–1** (phần cột/diện tích), KHÔNG phải số pixel, không phụ thuộc độ phân giải |
| `thresholds.green_min_width_px`, `marker_min_px` | Tính theo px ở 1920×1080, tự nhân theo tỉ lệ bề ngang màn hình (bề rộng tối thiểu vùng xanh / tổng pixel vàng tối thiểu quanh vạch) |
| `invert_pull` | Đặt `true` nếu thấy bot kéo **ngược chiều** (vạch vàng chạy xa vùng xanh) |
| `steering.*` | Độ nhạy điều khiển: `engage_frac`/`release_frac` (dead zone theo % bề rộng vùng xanh), `min_hold`, `marker_brake` (phanh quán tính) |
| `timings.*` | Các mốc thời gian chờ/timeout |
| `window_titles` | Chuỗi con của tiêu đề cửa sổ game (xem cột `fg=` của probe để biết tiêu đề thật) |

## Sự cố thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| Bot không bấm được phím trong game | Chạy PowerShell bằng **Run as Administrator** |
| Probe in `UNKNOWN` ở mọi màn hình | Sai chế độ hiển thị (để borderless), DLSS/FSR/HDR còn bật, hoặc ROI lệch — chạy `calibrate.py shot` |
| Bot kéo ngược chiều, cá thoát liên tục | Đặt `invert_pull: true` |
| Vạch vàng mất dấu lúc chiều tà | Câu vào ban ngày trong game, hoặc nới `hsv.yellow_marker` (giảm V min) |
| F8/F12 không ăn khi game focus | Cũng do thiếu quyền admin (UIPI chặn hook) |
| Bot không bấm gì, log im lặng | Tiêu đề cửa sổ game không khớp `window_titles` — xem `fg=` trong probe rồi thêm vào |
| A/D không ăn trong minigame dù bấm tay được | Có build game từng lỗi keyboard trong minigame (1.0.6) — cập nhật game |

## Cấu trúc

```
main.py        # vòng lặp chính + máy trạng thái + hotkey
vision.py      # chụp ROI qua mss, nhận diện trạng thái bằng HSV
ocr.py         # đọc số lượng mồi bằng RapidOCR (recognition-only, nạp lười)
fight.py       # điều khiển A/D bám vùng xanh (bù quán tính, hysteresis)
controller.py  # gửi phím/chuột qua PyDirectInput, kiểm tra focus
flows.py       # chuỗi thao tác UI: bấm "Bắt Đầu Câu Cá", bán cá (Q), đổi mồi (E), mua mồi (R)
humanizer.py   # nhân-hóa: trễ phản ứng, jitter, Bezier chuột, nghỉ, giới hạn phiên
calibrate.py   # công cụ căn chỉnh ROI/màu
smoke_test.py  # kiểm thử khô: khởi tạo mọi module, không gửi input
config.json    # toàn bộ tham số
```

Các luồng UI mới (flows.py) nhận diện bằng: nhãn hồng "Câu cá" + phím F (world —
chỉ để nhắc người dùng tự bấm F, bot không tự bấm), nút trắng "Bắt Đầu Câu Cá"
(prepare — nền tối phía trên chỉ là tín hiệu phụ), dải tiêu đề cam (Chợ Cá/FISHING
MASTER), viền hồng nút BÁN NHANH (trang khoang cá), cặp nút trắng trên nền tối
(hộp thoại 2 nút). Ô mồi: đếm màu chữ số lượng (trắng = còn, đỏ = 0), ô đang chọn
nhận bằng viền hồng hiện ở cả 4 cạnh. Mọi tọa độ là tỉ lệ của 1920×1080.

Shop mồi (R, `flows.buy_bait`): nhận diện bằng nút "Mua" trắng lớn dưới phải +
dải tiêu đề panel tối (`shop_buy_btn`/`shop_panel_top`); lưới item 3 ô/hàng theo
`bait_shop.grid_*` (gốc = tâm ô 1, đếm trái→phải rồi xuống hàng); số lượng chỉnh
bằng cách bấm `plus_btn` lặp (mặc định shop là 1, mỗi cú +1); thiếu sò nhận biết
qua số "Tiêu hao" chuyển đỏ (`shop_cost` + `red_text`) → bấm `minus_btn` giảm
dần, không mua nổi 1 thì bỏ. Vì bot không OCR được con số nên main.py giữ "sổ
mồi" ước tính: `assume_stock` khởi điểm, −1 mỗi lần thả cần, +N khi mua, =0 khi
hộp thoại đổi mồi báo hết sạch; trước khi thả cần so sổ với số cá còn phải câu
tới mốc bán (`_bait_needed`) để quyết định mua trước.

**Flow check mồi:** ngay sau khi `flows.start_from_prepare()` đưa vào chế độ câu
(và mỗi lần f10 chạy tiếp), main.py bật cờ `_need_bait_check` để mở hộp thoại E
đọc số mồi **TRƯỚC lần thả cần đầu tiên** — vì menu R/Q/E chỉ hoạt động sau khi
đã "Bắt Đầu Câu Cá". Thiếu mồi cho chu kỳ bán kế (`_bait_needed`) thì vào shop R
mua trước rồi mới thả cần.

**Đọc số mồi (OCR thật):** `vision._ocr_badge_count` crop badge số lượng của ô
đang chọn, gộp mask trắng+đỏ thành chữ nét đậm rồi phóng to 6× đưa vào
`ocr.read_int` (RapidOCR recognition-only, `use_det=False`). RapidOCR dùng model
ONNX của PaddleOCR — offline, đa ngôn ngữ, đọc số ~20ms/crop. `ocr.read_int`
chuẩn hóa nhầm lẫn chữ↔số (〇→0, l→1...) rồi lấy cụm chữ số đầu tiên. `bait_slots`
trả `count` (int hoặc None); `has_stock` suy từ `count>0` khi đọc được, lùi về
heuristic trắng/đỏ khi OCR trượt. main.py `_refresh_bait_count` ghi thẳng
`bait_left=count` (`_bait_exact=True`). Mở được hộp thoại nhưng OCR trượt số thì
dùng has_stock thô; chỉ tắt theo dõi (`_bait_watch=False`) sau **3 lần liên tiếp
KHÔNG mở được** hộp thoại E (`_bait_read_fails`), không tắt vĩnh viễn vì 1 lần lỗi.

Nếu chưa cài `rapidocr-onnxruntime` thì `ocr.available()` trả False, `count=None`,
bot lùi về cơ chế cũ (phản ứng khi `switch_bait` báo hết sạch). Đóng gói exe phải
gom model qua `collect_all` trong `AutoFishingNTE.spec` (build.bat dùng file spec).

**Đổi mồi quét hết ô (vuốt ngang):** hộp thoại E chỉ hiện ~5 ô; `flows.switch_bait`
đọc trang hiện tại, nếu mồi đang dùng còn hàng thì thôi (`bait_ok`), chưa thấy ô
nào còn hàng thì `_scroll_bait_strip` kéo-thả chuột ngang (`controller.drag`, từ
`bait_dialog.scroll.from_x`→`to_x` tại `scroll.y`) để lộ ô bên phải, lặp tới khi
gặp ô còn hàng / `bait_strip_sig` không đổi (chạm cuối) / hết `scroll.max_pages`.
Đổi sang **ô đầu tiên còn hàng từ trái** rồi bấm "Thay đổi". `vision.bait_strip_sig`
chụp ảnh xám 80×20 của cả dải ô, `strip_changed` so trung bình sai khác để biết
đã cuộn được hay chưa. Tham số kéo (steps, max_pages, tọa độ) ở `bait_dialog.scroll`
— chỉnh nếu game cuộn quá nhiều/ít. `shop_item_index` vẫn quyết định loại mồi mua
ở shop R (không liên quan tới việc quét ô khi đổi).

Humanizer (humanizer.py) tập trung mọi tính ngẫu nhiên: reaction lệch phải có
đuôi chậm, jitter hold/gap/settle, fatigue tăng theo giờ, micro/long break,
đường chuột Bezier bậc 2 + overshoot, click offset Gauss, session limit ngẫu
nhiên. Các module nhận instance qua tham số `human` (None = tắt, dùng cho test).
