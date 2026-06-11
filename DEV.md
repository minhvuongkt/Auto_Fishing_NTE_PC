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
- Mồi câu bị trừ mỗi lần thả cần; bot sẽ tự tạm dừng và kêu *beep* khi nghi hết mồi.

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
fight.py       # điều khiển A/D bám vùng xanh (bù quán tính, hysteresis)
controller.py  # gửi phím/chuột qua PyDirectInput, kiểm tra focus
calibrate.py   # công cụ căn chỉnh ROI/màu
smoke_test.py  # kiểm tra nhanh stack chụp màn hình + nhận diện (không gửi phím)
config.json    # toàn bộ tham số
```
