# NTE Auto Fishing — Hướng dẫn sử dụng

Tool tự động câu cá cho game **NTE (Neverness to Everness)**. Bạn chỉ cần đứng
tại điểm câu và bật tool — mọi thứ còn lại tool tự làm: thả cần, phát hiện cá
cắn, giật cần, tự căn chỉnh kéo cá, nhận cá và lặp lại liên tục.
Bot đọc màn hình (OpenCV + mss) và giả lập phím (SendInput scancode qua)
---

## 1. Tool làm được gì?

| Chức năng | Mô tả |
|---|---|
| Tự thả cần | Tự bấm F khi đang ở trạng thái sẵn sàng câu |
| Tự phát hiện cá cắn | Nhận diện vòng sáng xanh quanh nút F và giật cần ngay lập tức (nhanh hơn người) |
| Tự chơi minigame kéo cá | Điều khiển A/D đưa vạch vàng bám theo vùng xanh, có tính trước quán tính của vạch nên không bị vọt lố |
| Tự nhận cá | Tự bấm đóng màn kết quả rồi thả cần tiếp |
| Lặp vô hạn | Chu trình chạy liên tục cho đến khi bạn dừng |
| Thống kê | Đếm số cá bắt được, số lần kéo, thời gian chạy — hiện khi tạm dừng/thoát |
| Tự bảo vệ | Tự tạm dừng + kêu **beep** khi nghi hết mồi hoặc chờ lâu không có cá; tự nhả hết phím khi tạm dừng |
| 🪟 An toàn cửa sổ | Chỉ bấm phím khi cửa sổ game đang mở phía trước — alt-tab ra ngoài là tool tự ngưng bấm |

**Tool KHÔNG có các chức năng:** tự mua mồi, tự bán cá, tự di chuyển đến điểm
câu, chạy ngầm khi game thu nhỏ. Bạn cần chuẩn bị đủ mồi trước khi treo.

---

## 2. Chuẩn bị trước khi dùng (quan trọng!)

Cài đặt trong game — làm **một lần duy nhất**:

- Chế độ hiển thị: **Borderless / Windowed Fullscreen** (không dùng Fullscreen exclusive)
- **TẮT** DLSS / FSR / Frame Generation
- **TẮT** HDR và các bộ lọc màu
- Game đặt ở **màn hình chính**, khuyến nghị độ phân giải **1920×1080**
- Nên câu vào **ban ngày trong game** — lúc hoàng hôn/bình minh ánh vàng làm tool khó nhìn thấy vạch vàng

Ngoài game:

- Chuẩn bị **đủ mồi câu** (mỗi lần thả cần tốn 1 mồi)
- Windows scale nên để 100% (Settings → Display)

---

## 3. Cách chạy

### Cách 1 — File exe (dễ nhất)

1. Mở thư mục đã tải tool về, double-click **`NTE-AutoFishing.exe`**
2. Windows hỏi quyền Administrator → bấm **Yes** (bắt buộc, không có quyền này tool không bấm phím vào game được)

> File `config.json` phải luôn nằm **cùng thư mục** với file exe.
> Nếu antivirus báo nhầm/xóa file exe: thêm thư mục tool vào danh sách ngoại lệ
> (exclusion), hoặc dùng Cách 2 — kết quả giống hệt nhau.

### Phím điều khiển

| Phím | Tác dụng |
|---|---|
| **F8** | Bắt đầu / Tạm dừng (có tiếng beep xác nhận) |
| **F12** | Thoát tool, in thống kê phiên câu |

---

## 4. Quy trình sử dụng từng bước

1. Vào game, đi đến điểm câu cá, vào chế độ câu (thấy nút **F** hình móc câu ở góc phải dưới như khi câu tay).
2. Chạy tool. Tool khởi động ở trạng thái **tạm dừng** — chưa làm gì cả.
3. Click chuột vào cửa sổ game cho game nổi lên trước, rồi bấm **F8**. Nghe tiếng beep cao = tool bắt đầu chạy.
4. Ngồi xem hoặc đi làm việc khác... (không alt-tab — tool cần cửa sổ game mở phía trước).
5. Muốn nghỉ: bấm **F8** (beep trầm = đã dừng, tool nhả hết phím). Muốn tắt hẳn: **F12**.

### Đọc cửa sổ log

```
[19:02:11] Thả cần (F)...
[19:02:25] (!) Cá cắn câu → F
[19:02:27] (>) Bắt đầu kéo cá (lần 3)...
[19:02:41] Kéo cá kết thúc — chờ màn kết quả...
[19:02:43] <>< Bắt được cá! (tổng: 3)
```

| Thông báo | Ý nghĩa |
|---|---|
| `Cá thoát / đứt dây — thả lại` | Sẩy con đó, tool tự câu tiếp — bình thường |
| `Chờ lâu không có cá cắn — thu cần, thả lại` | Quá 90 giây không cá cắn, tool tự làm mới |
| `[!] Tạm dừng: thả cần không có tác dụng...` | **Nhiều khả năng hết mồi** — mua thêm mồi rồi bấm F8 chạy tiếp |
| `[!] Tạm dừng: 3 lần liên tiếp không có cá cắn` | Điểm câu có vấn đề (sai mồi/sai chỗ) — kiểm tra rồi F8 |

---

## 5. Tinh chỉnh nhanh (file `config.json`)

Mở `config.json` bằng Notepad, chỉ cần quan tâm mấy dòng này:

| Dòng | Khi nào cần sửa |
|---|---|
| `"invert_pull": false` | Nếu thấy tool kéo **ngược chiều** (vạch vàng cứ chạy xa vùng xanh) → đổi thành `true` |
| `"window_titles": [...]` | Nếu tool không bấm phím dù game đang mở → tên cửa sổ game không khớp, thêm tên đúng vào (xem mục 6) |
| `"hotkeys"` | Đổi phím F8/F12 nếu trùng phím khác bạn dùng |
| `"bite_timeout": 90.0` | Thời gian tối đa chờ cá cắn (giây) trước khi thu cần thả lại |

Sửa xong lưu file rồi khởi động lại tool. **Không cần build lại exe** — exe đọc
config mỗi lần mở.

---

## 6. Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| Tool chạy nhưng game không nhận phím | Chưa có quyền Administrator — chạy lại exe và bấm Yes |
| Bấm F8 không có phản ứng | Cũng do thiếu quyền admin (Windows chặn phím tắt khi game elevated) |
| Tool không bấm gì, log im lặng | Cửa sổ game không phải cửa sổ đang mở phía trước, hoặc `window_titles` không khớp (mục 6) |
| Tool kéo cá ngược chiều | `invert_pull: true` (mục 5) |
| Không nhận diện được gì ở mọi màn hình | Kiểm tra lại mục 2: borderless? DLSS/FSR/HDR đã tắt? |
| Hay mất dấu vạch vàng lúc chiều tà | Câu ban ngày trong game |
| Antivirus chặn/xóa file exe | Thêm ngoại lệ cho thư mục tool |
| Đứng màn kết quả không tự đóng | Chạy probe (mục 6) ở màn kết quả xem `RESULT` có hiện không |

---

## 7. Câu hỏi thường gặp

**Treo tool qua đêm được không?**
Không khuyến khích. Game cấm macro trong điều khoản và có anti-cheat ACE; tool
chỉ đọc màn hình + giả lập phím (không can thiệp vào game) nhưng **rủi ro khóa
tài khoản luôn tồn tại**, nhất là khi chạy quá đều đặn trong thời gian dài.
Chạy phiên ngắn vài chục phút và trông chừng là an toàn nhất. Bạn tự chịu trách
nhiệm khi sử dụng.

**Thu nhỏ game để làm việc khác trên máy được không?**
Không. Tool cần nhìn thấy màn hình game và cửa sổ game phải đang mở phía trước.
Alt-tab ra ngoài thì tool tự ngưng bấm phím (an toàn) và sẽ chạy tiếp khi bạn
quay lại game.

**Tool có dùng được ở độ phân giải khác 1920×1080?**
Có — mọi vùng nhận diện tự co giãn theo tỉ lệ. Nhưng 1920×1080 là độ phân giải
đã được kiểm chứng kỹ nhất; nếu dùng độ phân giải khác, nên chạy probe (mục 6)
kiểm tra một lượt trước khi treo.

**Hết mồi thì sao?**
Tool tự phát hiện (thả cần không có tác dụng), kêu beep và tạm dừng. Mua thêm
mồi ở tiệm cá rồi bấm F8 chạy tiếp.

**Cá hiếm tool có bắt được không?**
Được — cá hiếm có vùng xanh hẹp hơn và chạy nhanh hơn, tool được thiết kế bám
theo có dự đoán nên vẫn xử lý tốt. Nếu thấy hay sẩy cá hiếm, có thể nhờ người
chỉnh tinh các thông số `steering` trong config.
