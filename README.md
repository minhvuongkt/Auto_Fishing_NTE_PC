# NTE Auto Fishing

- Tool tự động câu cá game **NTE**. 
- Bạn chỉ cần đứng tại điểm câu và bật tool — mọi thứ còn lại tool tự làm: thả cần, phát hiện cá cắn, giật cần, kéo cá, nhận cá và lặp lại.
- Bot đọc màn hình và giả lập phím
---

## 1. Chức năng tool

| Chức năng | Mô tả |
|---|---|
| Tự thả cần | Tự bấm F khi đang ở trạng thái sẵn sàng câu |
| Tự phát hiện cá cắn | Nhận diện vòng sáng xanh quanh nút F và giật cần ngay lập tức (nhanh hơn người) |
| Tự kéo cá | Điều khiển A/D đưa vạch vàng bám theo vùng xanh, có tính trước quán tính của vạch nên không bị vọt lố |
| Tự nhận cá | Tự bấm đóng màn kết quả rồi thả cần tiếp |
| Lặp vô hạn | Chu trình chạy liên tục cho đến khi bạn dừng |
| Thống kê | Đếm số cá bắt được, số lần kéo, thời gian chạy — hiện khi tạm dừng/thoát |
| [X] Tự bảo vệ | Tự tạm dừng + kêu **beep** khi nghi hết mồi hoặc chờ lâu không có cá; tự nhả hết phím khi tạm dừng |
| An toàn cửa sổ | Chỉ bấm phím khi cửa sổ game đang mở phía trước — alt-tab ra ngoài là tool tự ngưng bấm |
| Tự bắt đầu câu | Bạn tự bấm F vào điểm câu; thấy bảng chuẩn bị là tool tự bấm "Bắt Đầu Câu Cá" (tool không tự bấm F vào điểm câu) |
| [X] Tự bán cá | Cứ đủ N con (mặc định 20) tự mở Chợ Cá (Q) → khoang cá → BÁN NHANH → Xác nhận → câu tiếp |
| [X] Tự đổi mồi | Hết mồi đang dùng thì tự mở hộp thoại đổi mồi (E), **vuốt ngang xem hết các ô**, đọc số lượng từng ô và đổi sang loại đầu tiên còn hàng |
| Tự mua mồi | Theo dõi số mồi còn lại, trước khi thả cần so với số cá cần câu tới lần bán kế — thiếu thì tự mở shop (R), chọn loại mồi đã cấu hình, chỉnh số lượng và Mua (tự giảm nếu không đủ sò) |
| Thao tác giống người | Phản ứng nhanh chậm ngẫu nhiên, di chuột theo đường cong, thi thoảng "ngó lơ" vài giây, tự nghỉ khi hết phiên |

**Lưu ý: [X] là đang trong giai đoạn thử nghiệm, sẽ có lỗi xảy ra, ae nhớ chú ý tránh mất công nhé!

**Tool KHÔNG có các chức năng:** tự di chuyển đến điểm câu, tự bấm F vào điểm
câu (bạn tự vào, tool nhắc trong log), chạy ngầm khi game thu nhỏ.

> Lưu ý về **tự bán cá**: nút BÁN NHANH của game bán **toàn bộ khoang cá**,
> kể cả vật phẩm hiếm câu được. Nếu muốn giữ cá lại, tắt bằng
> `"auto_sell": { "enabled": false }` trong config.

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

1. Mở thư mục đã tải tool về, double-click **`NTE-AutoFishing.exe`**
2. Windows hỏi quyền Administrator → bấm **Yes** (bắt buộc, không có quyền này tool không bấm phím vào game được)

> File `config.json` phải luôn nằm **cùng thư mục** với file exe.
> Nếu antivirus báo nhầm/xóa file exe: thêm thư mục tool vào danh sách ngoại lệ (exclusion).

### Phím điều khiển

| Phím | Tác dụng |
|---|---|
| **F10** | Bắt đầu / Tạm dừng (có tiếng beep xác nhận) |
| **F12** | Thoát tool, thống kê phiên câu |

---

## 4. Quy trình sử dụng từng bước

1. Vào game, đi đến điểm câu cá, vào chế độ câu (thấy nút **F** hình móc câu ở góc phải dưới như khi câu tay).
2. Chạy tool. Tool khởi động ở trạng thái **tạm dừng** — chưa làm gì cả.
3. Click chuột vào cửa sổ game cho game nổi lên trước, rồi bấm **F10**. Nghe tiếng beep cao = tool bắt đầu chạy.
4. Ngồi xem hoặc đi làm việc khác... (không alt-tab — tool cần cửa sổ game mở phía trước).
5. Muốn nghỉ: bấm **F10** (beep trầm = đã dừng, tool nhả hết phím). Muốn tắt hẳn: **F12**.

## 5. Tinh chỉnh nhanh (file `config.json`)

Mở `config.json` bằng Notepad, chỉ cần quan tâm mấy dòng này:

| Dòng | Khi nào cần sửa |
|---|---|
| `"invert_pull": false` | Nếu thấy tool kéo **ngược chiều** (vạch vàng cứ chạy xa vùng xanh) → đổi thành `true` |
| `"window_titles": [...]` | Nếu tool không bấm phím dù game đang mở → tên cửa sổ game không khớp, thêm tên đúng vào (xem mục 6) |
| `"hotkeys"` | Đổi phím F10/F12 nếu trùng phím khác bạn dùng |
| `"bite_timeout": 90.0` | Thời gian tối đa chờ cá cắn (giây) trước khi thu cần thả lại |
| `"flows" → "auto_sell" → "every_catches_min/max"` | Bán cá sau ngẫu nhiên 14–28 con (mỗi lần bán xong bốc mốc mới, không cố định); `"enabled": false` để tắt hẳn |
| `"flows" → "auto_switch_bait"` | `false` nếu muốn tự quản lý mồi |
| `"flows" → "auto_buy_bait" → "enabled"` | `false` nếu không muốn tool tự mua mồi ở shop (R) |
| `"flows" → "auto_buy_bait" → "shop_item_index"` | Ô mồi muốn mua trong shop, đếm **từ 1, trái → phải rồi xuống hàng** (mỗi hàng 3 ô). Mặc định `1` = Mồi Câu Đa Năng |
| `"flows" → "auto_buy_bait" → "buy_amount"` | Số mồi mua mỗi lần. Đặt `0` = tự tính theo auto sell (mua đủ câu tới lần bán kế + 20% dư); không đủ sò thì tool tự giảm số lượng |
| `"flows" → "auto_buy_bait" → "assume_stock"` | Số mồi bạn **đang có lúc bật tool**. Đặt `0` (mặc định) = tool tự mở hộp thoại mồi (E) trước khi câu và **đọc đúng số mồi còn lại bằng OCR** rồi trừ dần theo mỗi lần thả cần, cạn thì mở E đọc lại. Chỉ cần khai số nếu muốn bỏ qua bước đọc OCR đầu tiên |
| `"flows" → "auto_enter_fishing"` | `false` nếu không muốn tool tự bấm nút "Bắt Đầu Câu Cá" khi bảng chuẩn bị đang mở |
| `"humanize" → "enabled"` | `false` để tắt toàn bộ cơ chế giống người (phản ứng sẽ nhanh máy móc — không khuyến khích) |
| `"humanize" → "session_minutes_min/max"` | Khoảng thời lượng phiên; hết giờ tool tự tạm dừng để nghỉ |

Sửa xong lưu file rồi khởi động lại tool.

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

## 7. Q&A

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

**Hết mồi thì sao? Tool kiểm tra mồi trước khi câu thế nào?**
Ngay sau khi bấm "Bắt Đầu Câu Cá" để vào chế độ câu (và mỗi lần bấm F8 chạy
tiếp), **trước lần thả cần đầu tiên** tool mở nhanh hộp thoại đổi mồi (E) và
**đọc đúng con số mồi còn lại bằng OCR** (ví dụ thấy "43" là biết còn 43 cái).
Số này trừ dần mỗi lần thả cần và so với số cá còn phải câu tới lần bán kế:
**thiếu là tự vào shop (R) mua trước**, cạn thì mở E đọc lại. Thêm 2 lớp dự
phòng: hết mồi đang gắn → đổi sang loại còn hàng (E); hết sạch mọi loại → mua ở
shop (R). Chỉ khi mua cũng thất bại (hết sò chẳng hạn) tool mới beep và tạm dừng.

> OCR dùng thư viện RapidOCR chạy offline (đa ngôn ngữ, không gửi gì lên mạng).
> Nếu chạy từ source mà chưa cài, gõ `pip install -r requirements.txt`. Bản
> đóng gói `.exe` đã nhúng sẵn — không cần cài gì thêm.

**Mồi tool mua có đúng loại tôi muốn không?**
Tool mua theo `shop_item_index` — vị trí ô trong shop R, đếm từ 1, trái sang
phải rồi xuống hàng dưới (mỗi hàng 3 ô). Mặc định là ô 1 (Mồi Câu Đa Năng, 5
sò/cái, dùng được mọi vùng nước). Muốn loại khác thì đổi số thứ tự trong config.

**Cơ chế "giống người" hoạt động thế nào, có tắt được không?**
Tool tự thêm: độ trễ phản ứng ngẫu nhiên ~0.2–0.4s khi giật cần (thỉnh thoảng
chậm hẳn như người lơ đãng), thời gian giữ phím/khoảng nghỉ dao động, di chuột
theo đường cong có khi vọt quá đích, điểm click lệch quanh tâm nút, nghỉ vặt
vài giây ngẫu nhiên giữa các con cá, phản ứng chậm dần theo thời gian (mệt mỏi),
và mỗi phiên chỉ chạy 40–75 phút rồi tự nghỉ. Tắt bằng `"humanize": { "enabled": false }`
— nhưng để bật sẽ an toàn hơn trước anti-cheat hành vi.

**Cá hiếm tool có bắt được không?**
Được — cá hiếm có vùng xanh hẹp hơn và chạy nhanh hơn, tool được thiết kế bám
theo có dự đoán nên vẫn xử lý tốt. Nếu thấy hay sẩy cá hiếm, có thể nhờ người
chỉnh tinh các thông số `steering` trong config.
