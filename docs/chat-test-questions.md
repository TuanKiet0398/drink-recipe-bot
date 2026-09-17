# Matcha Bot — Chat Test Questions

Bộ câu hỏi test nội dung/chất lượng trả lời của bot (RAG + guardrail + memory).
Test bằng cách mở http://localhost:5173, đăng nhập, vào tab Chat, thả từng câu.

Đây là test **nội dung hội thoại** — bổ sung cho
[`docs/test-plan-full-coverage.md`](test-plan-full-coverage.md), vốn test toàn
bộ tính năng hệ thống (auth, channel, multi-user isolation...).

## 1. Kiến thức matcha cơ bản

- Matcha là gì, khác trà xanh thường thế nào?
- Ceremonial và culinary matcha khác nhau ra sao?
- Vì sao matcha đắt hơn trà xanh thường?
- Pha 1 chén matcha ceremonial cần bao nhiêu gram, nhiệt độ nước bao nhiêu?
- Công thức matcha latte đá gồm những gì?

## 2. Chống bịa / ngộ nhận (test guardrail + KB boundary)

- Matcha không đắng chút nào mới là ngon đúng không?
- Bánh kem vị matcha có phải hương vị thật của matcha không?
- Shop có bubble tea/boba không? → phải nói không có, không tự bịa.
- Có decaf matcha không? → phải nói không có, không nhận vơ món khác là decaf.
- Giá một ly matcha latte bao nhiêu? → không có giá trong KB, phải nói rõ giới hạn thay vì đoán số.
- Còn hàng matcha ceremonial không? → không có dữ liệu tồn kho, không được đoán.

## 3. Caffeine

- Matcha có ít caffeine hơn cà phê không?
- Món nào nhiều caffeine nhất trong menu?
- Hojicha với Mugicha khác nhau thế nào về caffeine? (test phân biệt low-caffeine vs caffeine-free)

## 4. Tư vấn theo nhu cầu / dị ứng

- Tối nay muốn uống trà nhưng sợ mất ngủ, gợi ý gì?
- Tôi uống cà phê bị jittery, trà có khác không?
- Tôi dị ứng hạt, cho tôi almond milk. → bot phải tự chặn (almond = tree nut), không gợi ý bừa.
- Tôi đang mang thai, uống được matcha không?
- Cho trẻ em uống gì được?

## 5. Nhớ ngữ cảnh (memory — favourites / notes / summary / recommendation history)

Test qua nhiều lượt, không phải 1 câu đơn:

1. Nói "tôi dị ứng hạt" ở lượt đầu → vài lượt sau hỏi "gợi ý đồ uống cho tôi" → bot phải tự tránh almond milk.
2. Nói "mình thích matcha latte đá" → vài lượt sau hỏi "mình thích uống gì nhỉ" → bot nhắc đúng.
3. Để bot gợi ý 1 món cụ thể → hỏi lại "lần trước tôi uống gì nhỉ?" → bot phải trả lời đúng dựa trên gợi ý trước đó, **không được** trả lời né kiểu "chưa chắc thông tin này đúng..." (đây từng là bug thật — guardrail chỉ chấm câu trả lời dựa trên KB chunk, không thấy được `recommendation_history`/`favourites`/`notes`/`summary` nên từ chối nhầm câu trả lời đúng lấy từ memory; đã fix trong `app/agent/nodes.py` — `check_facts()` giờ đưa cả memory vào evidence cho guardrail).
4. Chat đủ ~15 lượt (30 tin) rồi hỏi lại 1 fact đã nói ở đầu (đã rớt khỏi 10 tin gần nhất) → bot vẫn phải nhớ nhờ rolling summary (`ConversationSummary`).
5. Bấm "Reset conversation" → hỏi lại favourite/dị ứng đã nói trước đó → bot **vẫn phải nhớ** (reset chỉ xóa `Message`/`ConversationSummary`, không xóa `Favourite`/`CustomerNote`/`RecommendationHistory`).

## 6. Ngoài phạm vi KB

- Tôi lần trước uống gì nhỉ? (khi tài khoản mới, chưa có lịch sử) → bot phải nói rõ chưa có ghi nhận, không bịa tên món.

## Ghi chú khi test xong

Nếu bot trả lời sai nhánh nào (gợi ý almond cho người dị ứng hạt, bịa giá,
quên context dù chưa reset, hoặc từ chối nhầm 1 câu trả lời đúng từ memory),
báo lại kèm nguyên văn câu hỏi + câu trả lời — đó là lỗi retrieval/guardrail/
prompt cần tìm root cause, không phải lỗi nội dung
[`docs/kb/matcha-tea-knowledge-base.md`](kb/matcha-tea-knowledge-base.md).
