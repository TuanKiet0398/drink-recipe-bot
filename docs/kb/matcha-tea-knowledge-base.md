# Knowledge Base Toàn Diện về Trà & Matcha của Cửa Hàng

> **Mục đích:** Đây là nguồn kiến thức chuẩn (Single Source of Truth — SSOT) cho chatbot/tư vấn viên AI về matcha, các loại trà, nguyên liệu, caffeine, công thức pha chế, tùy chỉnh, dị ứng và hướng dẫn sức khỏe/lối sống được phép cung cấp.
>
> **Nguyên tắc quan trọng:** Nếu một đồ uống, nguyên liệu, thuộc tính hoặc tuyên bố không xuất hiện trong tài liệu này, chatbot **không được tự suy đoán hoặc bịa thông tin**. Khi thiếu dữ liệu, phải nói rõ rằng thông tin chưa có trong Knowledge Base và chuyển câu hỏi cho nhân viên khi cần.
>
> **Ghi chú ingest:** Upload file này qua Admin → Documents. Pipeline chunking tự động tạo embedding song ngữ (Việt/Anh) cho từng chunk, nên câu hỏi tiếng Việt của khách vẫn khớp đúng chunk dù nguồn viết bằng tiếng Việt.

---

## Phần 1 — Tổng quan & triết lý của cửa hàng

Cửa hàng chuyên về **matcha và các loại đồ uống từ trà**, được chuẩn bị theo phong cách của một tea house chuyên nghiệp: sử dụng lá trà thật và matcha chất lượng cao, pha bằng kỹ thuật đánh hoặc ngâm đúng cách, không sử dụng hỗn hợp bột pha sẵn hoặc syrup cô đặc để thay thế nguyên liệu chính.

Triết lý của cửa hàng:

1. **Hiểu sản phẩm trước khi tư vấn.** Không chỉ nói "ngon" mà phải giải thích được vì sao đồ uống có màu, mùi, vị và mức caffeine như vậy.
2. **Chọn đồ uống phù hợp với khách hàng**, thay vì cố bán món đang được ưa chuộng.
3. **Ưu tiên tính trung thực.** Nếu cửa hàng không có một sản phẩm, phải nói rõ và đưa ra lựa chọn gần nhất đang thực sự có trên menu.
4. **Không biến thông tin sức khỏe thành chẩn đoán y khoa.** Chỉ cung cấp thông tin caffeine/thành phần đã được ghi nhận trong KB.

### 1.1 Ba nguyên tắc tư vấn cốt lõi

**Nguyên tắc 1 — Match the drink to the person.** Khi tư vấn, ưu tiên: mức nhạy cảm với caffeine, thời điểm khách muốn uống, sở thích về vị (ngọt, đắng, grassy, floral, roasted, umami...), muốn đồ uống có sữa hay không, muốn nóng hay đá, dị ứng/thành phần cần tránh.

**Nguyên tắc 2 — Không đoán trong các câu hỏi nhạy cảm về sức khỏe.** Nếu khách hỏi về mất ngủ, mang thai, thuốc đang sử dụng, bệnh lý đã được chẩn đoán, hoặc caffeine và triệu chứng cá nhân — bot chỉ được sử dụng thông tin đã tài liệu hóa trong KB và nên khuyến nghị khách xác nhận với bác sĩ khi câu hỏi mang tính cá nhân/y khoa.

**Nguyên tắc 3 — Trung thực hơn "hospitality theater".** Không nói rằng cửa hàng có món không có trong menu. Không gọi một món khác là "decaf matcha" nếu thực tế không phải matcha đã khử caffeine.

---

## Phần 2 — Kiến thức nền tảng về trà & matcha

### 2.1 Matcha thực chất là gì?

Matcha là một loại trà xanh Nhật Bản đặc biệt, làm từ lá trà *Camellia sinensis* được che nắng trước khi thu hoạch, sau đó hấp, sấy khô (thành "tencha"), loại bỏ gân/cuống rồi nghiền mịn bằng cối đá thành bột có kích thước hạt cực nhỏ (khoảng 5–10 micron). Khác với trà xanh thông thường (ngâm rồi bỏ bã), matcha được đánh tan trực tiếp trong nước nóng và uống trọn cả lá trà ở dạng bột huyền phù.

Vì uống trọn lá, matcha đưa vào cơ thể **toàn bộ** hợp chất có trong lá (kể cả phần không tan trong nước), trong khi trà xanh pha thông thường chỉ chiết xuất các hợp chất tan trong nước rồi bỏ bã. Đây là lý do matcha luôn đậm đặc hơn hẳn về hương vị, caffeine và các hợp chất sinh học so với một tách trà xanh pha thông thường cùng khối lượng lá.

### 2.2 Quy trình sản xuất matcha

1. **Che nắng (shading):** khoảng 20–30 ngày (thường nói 3–4 tuần) trước thu hoạch, luống trà được che bằng lưới/mái đen để giảm ánh sáng mặt trời.
2. **Thu hái:** chỉ hái phần lá non nhất, thường là đợt thu hoạch đầu xuân (ichibancha).
3. **Hấp:** lá được hấp ngay sau khi hái để chặn quá trình oxy hóa — đặc trưng của trà xanh Nhật Bản nói chung.
4. **Sấy khô, loại bỏ gân và cuống:** phần thịt lá còn lại gọi là *tencha* — nguyên liệu thô của matcha.
5. **Nghiền mịn:** tencha được nghiền bằng cối đá truyền thống (chậm, ít sinh nhiệt, giữ màu và hương, chỉ ra vài chục gram/giờ) hoặc bằng máy nghiền công nghiệp (nhanh hơn nhưng dễ làm mất tinh tế của hương vị).

**Vì sao che nắng quan trọng:** giảm ánh sáng khiến cây trà tăng sản xuất chlorophyll (cho màu xanh đậm) và acid amin L-theanine (tạo vị umami, ngọt dịu), đồng thời giảm sự hình thành catechin gây đắng chát.

### 2.3 Năm yếu tố tạo nên hương vị matcha

Theo khảo sát trực tiếp với sáu nông dân trồng chè và sản xuất tencha tại Kyoto (gồm Uji), Shizuoka và Kagoshima, người sành matcha thường đánh giá đồng thời năm yếu tố sau:

| Yếu tố | Mô tả |
|---|---|
| **Umami** | Vị ngọt mặn đậm đà, đặc trưng của matcha cao cấp, đến chủ yếu từ L-theanine và acid amin tích lũy trong lá non được che nắng. |
| **Vị ngọt (amami)** | Không phải ngọt đường mà là sự tròn vị, dịu nhẹ theo sau umami, rõ nhất khi chén trà nguội bớt. |
| **Vị đắng – chát** | Không phải "kẻ thù" của umami, mà là khung giữ cho umami có chiều sâu — vị đắng vừa phải, dễ chịu chính là điều làm umami trở nên trọn vẹn. |
| **Hương thơm** | Thơm tươi, hơi giống cỏ non hoặc rong biển; theo các nông dân, đây thường là điều họ kiểm tra *đầu tiên* khi nếm trà của chính mình, trước cả màu sắc hay umami. |
| **Kết cấu & hậu vị (yoin)** | Matcha ngon phải mịn, hơi sánh như kem, và có dư vị kéo dài sau khi nuốt. |

### 2.4 Điều gì thực sự quyết định hương vị — không chỉ là che nắng

Quan niệm phổ biến cho rằng che nắng là yếu tố quyết định umami và độ ngọt của matcha. Tuy nhiên, khi được hỏi yếu tố nào ảnh hưởng nhiều nhất đến umami và độ ngọt (giữa: thời gian che nắng, giống chè, chăm bón đất, thời điểm thu hoạch, quy trình chế biến), **4/6 nông dân chọn việc quản lý đất và phân bón (hibai kanri)** là yếu tố quan trọng nhất — chỉ 1 người chọn che nắng.

Lý do: che nắng chỉ giúp cây "giữ lại" acid amin đã có sẵn trong lá, nhưng lượng acid amin đó được tích lũy từ nhiều tháng chăm bón đất trước đó. Chuỗi quyết định hương vị có thể tóm tắt:

> Đất và dinh dưỡng quyết định "trần" chất lượng → giống chè quyết định "tính cách" hương vị → che nắng cô đặc hương vị → thời điểm thu hoạch bắt trọn đỉnh điểm → quy trình chế biến bảo toàn tất cả.

### 2.5 Các giống chè (cultivar) phổ biến

Giống chè đóng vai trò như "giống nho" trong rượu vang — mỗi giống mang một tính cách hương vị riêng:

| Giống | Đặc trưng hương vị | Phù hợp cho đối tượng nào |
|---|---|---|
| **Asahi** | Giống Uji tuyển chọn, hương thơm nổi bật, umami tinh tế, thường dùng làm koicha (trà đặc) trong trà đạo — "quý tộc" trong các giống thu hoạch sớm. | Người sành trà lâu năm, muốn trải nghiệm koicha đúng chuẩn nghi thức, hoặc làm quà biếu cao cấp. |
| **Samidori** | Umami sâu, giàu hương, phù hợp làm tencha; umami "nhẹ nhàng, dễ chịu". | Người đã quen matcha, muốn nâng cấp lên hương vị sâu và giàu hơn cho việc uống hằng ngày. |
| **Ujihikari** | Umami sâu, nhiều lớp hương vị, khá hiếm. | Người thích sưu tầm, muốn thử trải nghiệm hiếm và đặc biệt. |
| **Saemidori** | Umami tươi mát, màu sắc và hương thơm nổi bật — "cửa ngõ" dễ tiếp cận nhất cho người mới bắt đầu với matcha đơn giống. | **Người mới bắt đầu** uống matcha nguyên bản; người thích vị tươi sáng, dễ chịu. |
| **Okumidori** | Màu xanh đậm, vị tròn trịa, êm dịu, không gắt. | Người muốn uống matcha mỗi ngày mà không sợ vị gắt; phù hợp uống buổi sáng. |
| **Gokō** | Hương thơm đậm, umami gần như béo ngậy; thường phối cùng Samidori trong các dòng matcha cao cấp. | Người thích hương thơm nổi bật, thường dùng trong các blend matcha cao cấp. |

Ở Kagoshima (miền Nam Nhật Bản), các giống phổ biến khác gồm Yabukita, Asatsuyu, Kanayamidori, Asanoka, Yutakamidori — cho hương vị đậm và tươi sáng hơn so với sự tinh tế nhiều lớp của matcha vùng Kyoto. Vùng trồng và giống chè luôn đi cùng nhau.

### 2.6 Thu hoạch đầu vụ và sau vụ: gốc rễ của phân loại Ceremonial – Culinary

- **Thu hoạch đầu vụ (first flush):** lá non nhất, được che nắng trọn thời gian, chứa lượng umami cao nhất trong năm. Đây là nguyên liệu cho **matcha ceremonial** — dùng để uống trực tiếp, không pha thêm sữa/đường.
- **Thu hoạch sau (second/third flush, thu hoạch mùa thu):** umami giảm, hương nhạt hơn. Loại lá này thường dùng cho **matcha culinary** (nấu ăn, làm bánh), trà sencha/bancha, hoặc trà đóng chai. Vị đắng mạnh hơn của culinary matcha thực chất là "công cụ" để hương vị trà không bị át bởi sữa, đường, bơ — không phải dấu hiệu chất lượng kém.

### 2.7 Ba ngộ nhận phổ biến về hương vị matcha

- **"Matcha ngon nhất là matcha không có chút đắng nào":** sai. Vị đắng vừa phải chính là thứ làm umami "có ý nghĩa". Một chén matcha hoàn toàn không có "cạnh" nào thường có vị rỗng, thiếu chiều sâu.
- **"Bánh/kem vị matcha là hương vị thật của matcha":** không đúng. Món tráng miệng thường dùng matcha culinary — loại có vị đắng mạnh, được chọn để "chọc thủng" lớp đường, sữa, kem. Chỉ biết matcha qua latte hay kem tức là mới nếm một *nguyên liệu*, chưa nếm trà thật.
- **"Càng tươi càng ngon":** bất ngờ nhất — theo một nghệ nhân lâu năm ở Uji, hương vị thật của matcha cần một giai đoạn "chín" (ủ) nhất định sau khi chế biến thành tencha; truyền thống Uji xưa có nghi lễ mở hũ trà vào mùa thu sau khi ủ qua hè. Tuy nhiên, sau khi đã **nghiền thành bột**, độ tươi lại cực kỳ quan trọng và nên dùng hết trong vài tuần.

### 2.8 Vì sao matcha tạo cảm giác khác cà phê

Matcha's caffeine đi cùng **L-theanine**, một amino acid gần như chỉ có ở cây trà, được cho là liên quan đến trạng thái tỉnh táo nhưng thư giãn (alpha-wave) và làm chậm tốc độ caffeine hấp thụ vào máu. Đây là lý do matcha thường mang lại cảm giác tỉnh táo êm dịu, kéo dài hơn và ít gây bồn chồn hơn so với cú tỉnh-rồi-tụt của cà phê — hữu ích khi khách nói cà phê làm họ lo âu/jittery nhưng vẫn muốn thứ gì đó có "lift". Đây là xu hướng phổ biến qua trải nghiệm người dùng, **không phải quy luật tuyệt đối** cho mọi cá nhân — không nên biến thành cam kết y khoa.

### 2.9 Matcha không phải là "cà phê"

Matcha đến từ cây trà (*Camellia sinensis*), còn cà phê đến từ cây cà phê (*Coffea*) — hai loài thực vật hoàn toàn khác nhau, dù nhiều quán bán chung.

### 2.10 Kiến thức cơ bản về quá trình chế biến trà (vì sao màu ≠ caffeine)

Tất cả trà xanh, oolong và trà đen đều từ cùng một loài cây, **Camellia sinensis**. Khác biệt chủ yếu đến từ quá trình chế biến và mức độ oxy hóa:

| Loại trà | Đặc điểm chế biến | Hương vị |
|---|---|---|
| Trà xanh | Gia nhiệt nhanh sau thu hoạch để hạn chế oxy hóa | Xanh, grassy, vegetal, nhẹ |
| Oolong | Oxy hóa một phần (khoảng 10–80%) | Từ floral/green đến roasted/dark |
| Trà đen | Oxy hóa hoàn toàn | Đậm, malty, đôi khi có dried fruit/honey |
| Hojicha | Trà xanh được rang sau chế biến | Nutty, roasted, caramel-like; rang cũng phá hủy phần lớn caffeine |

Không thể kết luận "trà càng đậm màu thì càng nhiều caffeine". Ví dụ: **Hojicha** có màu rang đậm nhưng caffeine thấp; **Gyokuro** có màu xanh nhạt nhưng có thể chứa lượng caffeine rất cao. Caffeine phụ thuộc vào loại lá, điều kiện trồng, mức độ che bóng, quá trình chế biến, lượng trà/bột sử dụng, và cách pha — không phải màu nước trà.

### 2.11 Sencha và Matcha

**Sencha** (煎茶) là loại trà xanh phổ biến nhất Nhật Bản, chiếm khoảng 70–80% sản lượng trà cả nước. Khác matcha, sencha trồng dưới ánh nắng trực tiếp (không che), hấp – vò – sấy thành lá kim nhỏ, rồi **pha bằng cách hãm rồi lọc bỏ bã** như trà thông thường.

| Đặc điểm | Sencha | Matcha |
|---|---|---|
| Dạng | Lá nguyên | Bột mịn |
| Canh tác | Trồng dưới nắng | Che nắng trước thu hoạch |
| Cách pha | Hãm rồi lọc | Đánh tan, uống cả bột |
| Hương vị | Tươi, cỏ non, thanh mát | Đậm, béo, umami rõ |
| Caffeine/tách | ~20–40 mg | ~38–88 mg |
| Vai trò | Trà uống hằng ngày | Trà đạo, quán café, ẩm thực cao cấp |

Hai loại trà này không cạnh tranh mà **bổ trợ nhau**: sencha cho sự thanh mát mỗi ngày, matcha cho những dịp cần sự đậm đà, nghi thức.

---

## Phần 3 — Bảng tham chiếu caffeine

> Các số liệu là **ước lượng trên khẩu phần tiêu chuẩn 240 ml (8 oz)** theo công thức chuẩn của cửa hàng. Không nên trình bày như một giá trị tuyệt đối — thực tế còn phụ thuộc lượng bột/lá, giống chè, thời điểm thu hoạch và cách pha.

| Nền đồ uống | Caffeine xấp xỉ | Mức tương đối | Phù hợp trước khi ngủ? |
|---|---:|---|---|
| Gyokuro | 70–90 mg | Rất cao | Không |
| Matcha ceremonial | 60–80 mg | Cao | Không |
| Matcha culinary (latte) | 40–60 mg | Trung bình-cao | Không |
| Trà đen | 40–70 mg | Trung bình-cao | Không |
| Oolong | 25–45 mg | Trung bình | Thận trọng buổi tối |
| Sencha | 25–40 mg | Trung bình | Thận trọng buổi tối |
| Genmaicha | 15–25 mg | Thấp | Có thể, ở mức vừa phải |
| Hojicha | 10–20 mg | Thấp | Có |
| Chamomile / Peppermint / Sả–gừng / Mugicha | 0 mg | Không có | Có |

Để tham chiếu, một số đồ uống ngoài menu thường được khách so sánh: cà phê phin/nhỏ giọt 240ml ~70–140mg; espresso 2 shot (~60ml) ~60–80mg; nước tăng lực lon 250ml ~80mg. Một tách cà phê thường có nhiều caffeine hơn một chén matcha cùng thể tích, nhưng khoảng giá trị có sự chồng lấn — một chén matcha đậm 2g có thể ngang bằng một tách cà phê nhẹ.

**Quy tắc tư vấn caffeine:** nếu khách nói mất ngủ, nhạy cảm với caffeine, caffeine làm lo âu/jittery, hoặc muốn uống trước khi ngủ — ưu tiên theo thứ tự: (1) Chamomile, (2) Mugicha hoặc Sả–gừng, (3) Peppermint, (4) Hojicha hoặc Genmaicha nếu khách vẫn muốn trà lá và chấp nhận một lượng caffeine thấp. **Không ưu tiên** Gyokuro, matcha ceremonial, matcha culinary, sencha, oolong hoặc trà đen cho khách đã nói caffeine ảnh hưởng đến giấc ngủ.

**Khuyến nghị caffeine hằng ngày tổng quát (không phải tư vấn y khoa):** người trưởng thành khỏe mạnh thường được khuyến nghị không quá 400 mg/ngày từ mọi nguồn; phụ nữ mang thai nhiều hướng dẫn khuyên giới hạn khoảng 200 mg/ngày; người nhạy cảm caffeine hoặc có vấn đề huyết áp nên bắt đầu với lượng nhỏ và theo dõi phản ứng cơ thể.

---

## Phần 4 — Họ Matcha

### 4.1 Matcha Ceremonial

**Đặc điểm:** lá non nhất, chất lượng cao, trồng dưới bóng, thu hoạch đầu vụ, nghiền bằng cối đá. Thiết kế để uống nguyên chất với nước — không mix sữa/đường.

**Hương vị:** ngọt tự nhiên, umami rõ, ít đắng nếu pha đúng.

**Caffeine:** 60–80 mg/khẩu phần.

**Phù hợp với ai:** người muốn trải nghiệm matcha nguyên bản, thích uống không sữa/không đường, không nhạy cảm với caffeine; phù hợp hơn vào buổi sáng hoặc đầu giờ chiều. Người mới bắt đầu nên chọn giống dễ uống (Saemidori/Okumidori), pha usucha (loãng), không thêm đường để cảm nhận đúng vị thật trước.

**Không nên:** dùng nước sôi hoàn toàn; thêm nhiều đường; trộn sữa nếu mục tiêu là trải nghiệm ceremonial truyền thống; pha đá (mất sự tinh tế của hương thơm).

**Công thức Usucha (trà loãng, cách phổ biến nhất) — Nóng, uống nguyên chất:**
- Nguyên liệu: 1–2g matcha ceremonial · 60–70ml nước ở 70–80°C (vừa sôi tới, không dùng nước đang sôi).
- Cách làm: (1) Rây bột matcha qua lưới mịn vào bát miệng rộng để tránh vón cục. (2) Rót khoảng 10ml nước nóng vào, dùng chasen đánh tan thành hỗn hợp sánh mịn như hồ. (3) Thêm phần nước còn lại, đánh nhanh theo hình chữ "M"/"W" (không khuấy vòng tròn) trong 15–20 giây tới khi có lớp bọt mịn phủ kín mặt, không còn cục khô. (4) Phục vụ ngay — matcha sẽ tách lớp và xẹp bọt sau vài phút, nên đây là món pha theo yêu cầu.

**Công thức Koicha (trà đặc, dùng trong nghi thức):**
- Nguyên liệu: 3–4g matcha cao cấp (thường Asahi hoặc Samidori) · 20–30ml nước khoảng 70°C (thấp hơn usucha một chút để tránh đắng phát sinh do lượng bột nhiều).
- Cách làm: nhào bột với nước thành hỗn hợp sánh mịn như mật ong đặc, khuấy chậm và đều tay bằng chasen — không đánh mạnh để tạo bọt như usucha.
- Phù hợp: người sành trà, dịp trà đạo trang trọng, muốn trải nghiệm matcha ở dạng cô đặc nhất.

### 4.2 Matcha Culinary

**Đặc điểm:** lá thu hoạch sau (second/third flush), nghiền bằng cối đá, vị mạnh hơn và hơi đắng/chát hơn ceremonial, chịu được sữa/đường/đá tốt.

**Hương vị:** grassy, đắng hơn ceremonial khi uống trơn, nhưng cân bằng đẹp với chất béo của sữa và chút ngọt.

**Caffeine:** 40–60 mg/khẩu phần, tùy lượng bột.

**Phù hợp:** lựa chọn mặc định cho matcha latte, iced matcha latte, và mọi đồ uống matcha pha sữa. Đa số khách nói "tôi thích matcha" nhưng không nói rõ "ceremonial nguyên chất" thực ra muốn loại này. Cũng là lựa chọn phù hợp hơn ceremonial cho nấu ăn/làm bánh vì bền màu và vị đủ đậm để không bị át bởi đường, sữa, bơ.

**Matcha Latte — Nóng:**
- Nguyên liệu: 2g culinary matcha · 30ml nước 80°C · 180ml sữa tùy chọn · 1–2 muỗng cà phê syrup đường (tùy mức đường khách chọn).
- Cách làm: (1) Rây matcha vào ly để tránh vón cục. (2) Cho nước nóng vào, đánh bằng chasen (hoặc dụng cụ đánh nhỏ) theo chuyển động zig-zag dứt khoát 15–20 giây tới khi mịn, không vón, có lớp bọt mỏng. (3) Hấp nóng sữa đến 65–70°C (không để sôi). (4) Rót sữa vào hỗn hợp matcha, khuấy đều trong lúc rót. (5) Thêm syrup theo mức đường khách chọn. (6) Phục vụ ngay trong ly đã làm ấm trước.

**Matcha Latte — Đá:**
- Nguyên liệu: 2g culinary matcha · 30ml nước nóng 80°C · 1–2 muỗng cà phê syrup đường · 150ml sữa lạnh tùy chọn · đá.
- Cách làm: (1) Rây matcha vào shaker/hũ có nắp. (2) Cho nước nóng và syrup vào. (3) Đóng nắp, lắc mạnh 15 giây (hoặc đánh mạnh bằng whisk) tới khi tan hoàn toàn và hơi sủi bọt — bước này quan trọng hơn ở bản đá vì không có bước hấp sữa hỗ trợ hòa tan. (4) Cho đá vào ly theo mức đá khách chọn. (5) Rót hỗn hợp matcha lên đá. (6) Rót thêm sữa lạnh lên trên, khuấy nhẹ.

**Tùy chỉnh:** mức đường (0%/25%/50%/75%/100%), mức đá (không đá/ít đá/đá bình thường), loại sữa (sữa bò nguyên kem, oat, soy, almond — xem Phần 12 về dị ứng).

### 4.3 Genmaicha-Matcha Blend

**Đặc điểm:** culinary matcha blend cùng gạo lứt rang (genmai) ở cấp độ lá.

**Hương vị:** nutty, toasty, gợi liên tưởng popcorn, cân bằng vị grassy của matcha; matcha vẫn hiện diện nhưng nhẹ hơn.

**Caffeine:** 20–35 mg/khẩu phần (thấp hơn matcha nguyên chất vì một phần thể tích là gạo rang, không phải lá trà).

**Phù hợp:** khách thích matcha nhưng muốn caffeine thấp hơn matcha latte thông thường, hoặc muốn vị ấm/dễ uống vào chiều tối. Đây cũng là câu trả lời chuẩn của shop khi khách hỏi "matcha nhưng ít caffeine".

**Genmaicha-Matcha Latte — Nóng/Đá:**
- Nguyên liệu: 3g hỗn hợp genmaicha-matcha · 30ml nước nóng 80°C · 1–2 muỗng cà phê syrup đường · 150–180ml sữa tùy chọn (hấp nóng cho bản nóng, để lạnh cho bản đá) · đá (chỉ bản đá).
- Cách làm (nóng): rây hỗn hợp vào ly, đánh với nước nóng thành hỗn hợp sánh mịn (cùng chuyển động "W" như matcha nguyên chất), hấp nóng sữa và trộn vào, khuấy syrup theo độ ngọt.
- Cách làm (đá): đánh hỗn hợp với nước nóng và syrup tới khi tan hết, rót lên đá, thêm sữa lạnh lên trên, khuấy đều.

### 4.4 Tác dụng phụ khi uống quá nhiều matcha

Vì uống trọn lá, matcha mang lượng caffeine và hợp chất thực vật cô đặc hơn trà thường — dùng quá mức hoặc sai cách có thể gây:

- **Bồn chồn, lo âu, tim đập nhanh:** do caffeine, đặc biệt khi dùng lượng lớn hoặc kết hợp thêm cà phê/nước tăng lực.
- **Khó chịu dạ dày:** nhất là uống lúc bụng đói — tannin và catechin có thể kích ứng niêm mạc dạ dày; uống cùng/sau bữa ăn thường giảm hiện tượng này.
- **Ảnh hưởng giấc ngủ:** caffeine tồn tại trong cơ thể nhiều giờ; hạn chế uống matcha chiều muộn nếu nhạy cảm.
- **Giảm hấp thu sắt:** polyphenol có thể liên kết với sắt non-heme (sắt thực vật), đáng lưu ý với người ăn chay/thiếu sắt — nên uống matcha cách xa bữa ăn giàu sắt.
- **Tăng nhịp tim/huyết áp nhẹ:** người nhạy cảm caffeine hoặc bệnh tim mạch nên theo dõi lượng dùng.
- **Chất lượng nguồn gốc:** cây trà có thể hấp thụ kim loại nặng từ đất, nên nguồn matcha minh bạch, quy trình canh tác rõ ràng là quan trọng.

**Cách giảm tác dụng phụ:** giảm lượng bột mỗi lần pha, tránh uống muộn trong ngày, không kết hợp nhiều nguồn caffeine cùng lúc, uống cùng thức ăn thay vì lúc bụng đói.

### 4.5 Nên chọn loại matcha nào theo phẩm cấp và nhu cầu

| Phẩm cấp | Đặc điểm | Phù hợp cho đối tượng |
|---|---|---|
| **Ceremonial** (thu hoạch đầu vụ) | Umami cao, ít đắng chát, màu xanh tươi, giá cao hơn | Uống trực tiếp (không đường/sữa); người mới tìm hiểu trà đạo; người sành trà; quà tặng |
| **Culinary** (thu hoạch sau) | Vị đậm, hơi đắng, chịu nhiệt và chịu trộn tốt, giá hợp lý hơn | Làm bánh, pha latte/sinh tố; quán café/tiệm bánh cần chi phí ổn định |

Theo mục đích và tình trạng cá nhân: người mới bắt đầu → ceremonial nhẹ (Saemidori/Okumidori), usucha, không đường; người cần tập trung học/làm việc → ceremonial buổi sáng/đầu chiều nhờ caffeine + L-theanine; người nhạy cảm caffeine/mang thai → lượng nhỏ (~1g/lần), tránh koicha đậm, theo dõi tổng caffeine trong ngày; người tập luyện thể thao/muốn ít calo → pha với nước/đá, không đường; người làm bánh/pha chế cho quán → culinary vì bền màu và giá hợp lý cho số lượng lớn; người ăn chay/nguy cơ thiếu sắt → vẫn dùng được, uống cách xa bữa ăn giàu sắt; người quen cà phê muốn chuyển sang matcha → bắt đầu bằng matcha latte rồi dần chuyển sang usucha nguyên bản.

### 4.6 Hạn sử dụng và bảo quản matcha

Matcha xuống cấp chất lượng nhanh hơn nhiều loại trà khác vì nghiền cực mịn (5–10 micron), diện tích tiếp xúc không khí tăng gấp hàng nghìn lần so với lá nguyên.

| Trạng thái | Đỉnh hương vị | Vẫn chấp nhận được | Vẫn dùng được (nếu khô ráo) |
|---|---|---|---|
| Chưa mở, đóng gói tốt | 6–12 tháng kể từ khi nghiền | Tới ~18 tháng | Có thể tới 24 tháng theo nhãn |
| Đã mở nắp | 4–8 tuần | 2–3 tháng | Vài tháng nếu bảo quản kỹ |

**"Bốn kẻ thù" của độ tươi matcha:** (1) Oxy — gây oxy hóa, mất màu, luôn đậy kín hộp sau khi dùng; (2) Ánh sáng — phá vỡ chlorophyll, nên dùng hộp/lọ không trong suốt; (3) Nhiệt độ — phản ứng hóa học nhanh hơn khi nóng, tránh để gần bếp/nắng; (4) Độ ẩm và mùi lạ — matcha dễ hút ẩm/mùi, có thể dẫn đến mốc, vón cục.

**Dấu hiệu xuống cấp:** màu chuyển từ xanh ngọc tươi sang xanh ô liu/vàng nâu; hương từ tươi mát sang nhạt như cỏ khô; kết cấu vón cục nếu hút ẩm; vị đắng gắt hơn, mất ngọt/umami, đôi khi tanh kim loại.

**Cách bảo quản:** dùng hộp kim loại kín khí, túi tráng bạc có khóa zip, hoặc lọ gốm sứ đục màu kín nắp. Dùng trong vài tuần: để tủ khô mát, tránh sáng là đủ. Bảo quản lạnh: phổ biến với matcha cao cấp, cần để hộp về nhiệt độ phòng hoàn toàn trước khi mở để tránh ngưng tụ hơi nước gây vón cục. Đông lạnh: dùng cho lưu trữ dài hạn, tránh mở/đóng nhiều lần. Matcha "qua đỉnh" nhưng còn khô, không mốc vẫn dùng tốt cho làm bánh/sinh tố/latte, nơi sữa-đường-bơ cân bằng lại hương vị đã nhạt.

**Dấu hiệu nên bỏ:** mốc/nấm nhìn thấy được, mùi chua/ẩm mốc nồng, vón cục ẩm cứng, hoặc bao bì thủng/ngấm nước.

---

## Phần 5 — Họ trà xanh

### 5.1 Sencha

**Hương vị:** grassy, hơi ngọt, astringency nhẹ. **Caffeine:** 25–40 mg. **Phù hợp:** trà xanh hằng ngày, nhẹ hơn matcha, ít dữ dội hơn gyokuro, uống nóng hoặc đá.

**Pha nóng:** 3g lá, 200ml nước 70–80°C, ngâm 60–90 giây; làm ấm bình bằng nước nóng trước rồi đổ bỏ để giữ nhiệt độ pha ổn định; không dùng nước sôi vì làm tăng vị đắng; có thể hãm lại lần 2 (thêm 10–15 giây) trước khi bỏ lá.

**Pha đá:** 6g lá, 100ml nước 70–80°C ngâm 60–90 giây (pha gấp đôi độ đậm vì đá sẽ làm loãng), lọc bỏ lá ngay để dừng chiết xuất, rót trà còn nóng lên ly đầy đá để làm lạnh nhanh và giữ hương tươi.

### 5.2 Gyokuro

Trà xanh Nhật Bản cao cấp và giàu caffeine nhất trong menu — được che nắng lâu hơn cả matcha (có thể vài tuần) trước thu hoạch.

**Hương vị:** umami mạnh, ngọt, giàu, đậm, gợi cảm giác seaweed-like, ít đắng.

**Caffeine:** 70–90 mg/khẩu phần — cao nhất menu, vì quá trình che bóng giúp tăng hương vị cũng đồng thời cô đặc caffeine.

**Phù hợp:** người sành trà muốn trải nghiệm hương vị đậm và phức tạp nhất. **Không khuyến nghị** cho khách nhạy caffeine, đang mang thai, hoặc quan tâm giấc ngủ.

**Pha:** 4g lá, 50–60ml nước ở 50–60°C (mát hơn hẳn các loại trà khác trong menu — cần để nước sôi nguội xuống, dùng nhiệt kế nếu có), ngâm 90 giây, lọc vào ly nhỏ; nhiệt độ thấp và lượng nước ít giúp giữ độ ngọt, tránh vị đắng gắt. Có thể hãm lại lần 2 với thời gian ngắn hơn (60–70 giây). **Không có bản đá** theo menu chuẩn — hương vị tinh tế sẽ mất khi bị pha loãng.

---

## Phần 6 — Nhóm trà rang, caffeine thấp

### 6.1 Hojicha

Trà xanh (thường từ thân và các đợt thu hoạch muộn hơn) được rang ở nhiệt độ cao sau chế biến — quá trình rang phá hủy phần lớn caffeine.

**Hương vị:** ấm, nutty, toasty, caramel-like, gần với cà phê rang về mùi nhưng không đắng, không nhiều caffeine.

**Caffeine:** 10–20 mg/khẩu phần — một trong những loại "trà lá thật" thấp caffeine nhất menu.

**Phù hợp:** lựa chọn hàng đầu cho khách nhạy cảm caffeine, dễ mất ngủ, hoặc muốn thứ gì ấm áp uống buổi tối không ảnh hưởng giấc ngủ. Cũng là gợi ý "thay thế cà phê" tốt cho người đang giảm caffeine nhưng vẫn nhớ vị rang.

**Pha nóng:** 3g, 200ml nước 90–95°C (hojicha chịu nhiệt tốt vì ít astringency để chiết), ngâm 30 giây.

**Hojicha Latte — Nóng:** làm nước cốt đậm bằng cách hãm 6g hojicha trong 80ml nước 90–95°C trong 3–4 phút (gấp đôi tỉ lệ lá/nước vì sẽ bị pha loãng bởi sữa), lọc bỏ lá, hấp nóng 180ml sữa đến 65–70°C, trộn nước cốt và sữa, thêm syrup theo mức đường khách chọn.

**Hojicha Latte — Đá:** hãm 6g trong 80ml nước 90–95°C 3–4 phút, lọc bỏ lá, khuấy syrup vào khi còn ấm để tan hết, cho đá vào ly, rót nước cốt lên đá rồi thêm 150ml sữa lạnh, khuấy đều.

### 6.2 Genmaicha

Trà xanh blend với gạo lứt rang (genmai), một số hạt nổ như bắp rang trong quá trình rang.

**Hương vị:** nutty, toasty, savory-sweet, nhẹ hơn hojicha, vị trà xanh rõ hơn.

**Caffeine:** 15–25 mg/khẩu phần.

**Phù hợp:** một lựa chọn mạnh khác cho khách nhạy caffeine/uống buổi tối nhưng vẫn muốn trà lá (không phải herbal).

---

## Phần 7 — Họ Oolong

### 7.1 Oolong nhẹ — Floral

**Chế biến:** oxy hóa nhẹ khoảng 10–20%, gần với trà xanh. **Hương vị:** floral, creamy, hơi ngọt. **Caffeine:** 25–35 mg. **Phù hợp:** khách thấy trà xanh quá grassy nhưng trà đen quá nặng — lựa chọn trung gian.

### 7.2 Oolong đậm — Roasted

**Chế biến:** oxy hóa và rang nhiều hơn, khoảng 40–80%. **Hương vị:** woody, fruity nhẹ, roasted finish, full-bodied. **Caffeine:** 35–45 mg. **Phù hợp:** khách muốn thứ gì ấm và đậm đà mà chưa cần tới trà đen. Khách nhạy caffeine nên thận trọng nếu uống buổi tối.

**Trà Sữa Oolong — Nóng/Đá:** hãm 6g dark oolong trong 100ml nước 95°C trong 4–5 phút để làm nước cốt đậm, lọc bỏ lá, hâm ấm/để lạnh 100–150ml sữa tùy bản, nêm syrup theo độ ngọt; bản đá rót nước cốt còn ấm lên đá rồi thêm sữa lạnh, khuấy đều.

---

## Phần 8 — Trà đen

### 8.1 Classic Black Tea

**Chế biến:** oxy hóa hoàn toàn. **Hương vị:** bold, malty, đôi khi có dried fruit/honey tùy nguồn gốc. **Caffeine:** 40–70 mg/khẩu phần — tương đương hoặc cao hơn một chén matcha tùy thời gian ngâm. **Phù hợp:** khách muốn vị "trà cổ điển" quen thuộc nhất, không ngại caffeine mạnh; nền tốt cho trà sữa. **Không nên** khuyến nghị cho khách hỏi về đồ uống dễ ngủ.

**Pha nóng:** 3g, 200ml nước 95–100°C, ngâm 3–4 phút — trà đen chịu được nước sôi tốt và cần ngâm lâu hơn để chiết hết vị đậm, mạch nha đặc trưng.

**Trà Sữa Đen — Nóng/Đá:** hãm 6g trong 100ml nước 95–100°C trong 4–5 phút để làm nước cốt, lọc bỏ lá, hâm ấm (65–70°C, bản nóng) hoặc để lạnh (bản đá) 100–150ml sữa, nêm đường theo mức khách chọn; bản đá cần khuấy kỹ hơn để hòa trộn hết vị đậm với sữa.

---

## Phần 9 — Nhóm trà thảo mộc không caffeine

Bốn lựa chọn sau có **0 mg caffeine** — nhóm ưu tiên hàng đầu khi khách nói mất ngủ, mang thai, cho trẻ em, hoặc chỉ đơn giản muốn uống gì đó ngay trước khi ngủ.

### 9.1 Chamomile

**Hương vị:** floral, hơi ngọt, gợi liên tưởng táo, có tiếng "làm dịu" tự nhiên. **Caffeine:** 0 mg. **Phù hợp:** câu trả lời tốt nhất cho "Tôi thích trà nhưng khó ngủ" — nên gợi ý chamomile đầu tiên.

**Pha nóng:** 1 túi lọc hoặc 2g hoa cúc khô, 220ml nước sôi hoàn toàn (95–100°C — hoa cúc chịu nước sôi tốt vì là trà hoa, không phải lá mỏng), ngâm 5 phút, đậy kín để giữ hương thơm dễ bay hơi, bỏ túi lọc/lọc hoa. Thêm ngọt nếu khách yêu cầu (mật ong cho người lớn; **không dùng mật ong cho trẻ dưới 1 tuổi**, dùng syrup đường thay thế).

**Pha đá:** gấp đôi độ đậm (2 túi lọc hoặc 4g trong 150ml), ngâm 5 phút đậy kín, thêm ngọt khi còn ấm, lọc rồi rót lên ly đầy đá.

### 9.2 Peppermint

**Hương vị:** mát, minty, refreshing, thường dùng để dịu dạ dày. **Caffeine:** 0 mg. **Phù hợp:** khách muốn caffeine-free nhưng vẫn tươi sáng thay vì buồn ngủ — lựa chọn tốt để uống đá quanh năm, không chỉ buổi tối.

**Pha nóng:** 1 túi lọc hoặc 2g lá khô, 220ml nước sôi hoàn toàn, ngâm 5–7 phút (lâu hơn hoa cúc một chút để chiết hết vị the mát), đậy kín, hiếm khi cần thêm ngọt.

**Pha đá:** gấp đôi độ đậm (2 túi lọc/4g trong 150ml), ngâm 5–7 phút đậy kín, lọc và rót nóng lên ly đầy đá để làm lạnh nhanh, giữ vị the mát.

### 9.3 Lemongrass-Ginger (Sả Gừng)

**Hương vị:** citrus từ sả, cay ấm từ gừng. **Caffeine:** 0 mg. **Phù hợp:** khách muốn thức uống caffeine-free nhưng vẫn có cảm giác "ấm và energizing" nhờ vị gừng — dùng khi khách muốn cảm giác tỉnh táo mà không cần chất kích thích thật sự.

**Pha nóng:** 1 cây sả tươi đập dập rồi cắt 3–4 đoạn, 5g gừng tươi thái mỏng, 220ml nước; đun sôi nhẹ (không sôi mạnh), giữ sôi nhẹ 5 phút — cần nấu sôi nhẹ chứ không chỉ ngâm để chiết hết vị cay của gừng; lọc và phục vụ.

**Pha đá:** gấp đôi độ đậm (2 cây sả, 10g gừng trong 150ml nước), sôi nhẹ 5 phút, lọc, thêm syrup nếu khách yêu cầu khi còn ấm, rót lên đá.

### 9.4 Roasted Barley — Mugicha (Lúa mạch rang)

Làm từ **hạt lúa mạch rang**, không phải lá trà. **Hương vị:** nutty, toasty, hơi ngọt, gần với hojicha nhưng hoàn toàn không caffeine. **Caffeine:** 0 mg. **Phù hợp:** khách muốn vị "rang thơm" giống hojicha/genmaicha nhưng cần 0 caffeine tuyệt đối (ví dụ đang mang thai, hoặc dùng thuốc tương tác với caffeine) — câu trả lời chuẩn khi khách nói "tôi thích hojicha nhưng hiện tại không được dùng chút caffeine nào".

**Pha nóng:** 10g lúa mạch rang, 220ml nước, đun sôi nhẹ và giữ sôi nhẹ 5–8 phút để chiết hết vị rang thơm (ngâm nhanh sẽ chiết chưa đủ, vị nhạt), lọc và phục vụ; vị ngọt-rang tự nhiên, hiếm khi cần thêm đường.

**Pha đá:** 15g hạt, 250ml nước, sôi nhẹ 8 phút (đậm hơn/lâu hơn bản nóng để bù phần bị pha loãng bởi đá), lọc và làm lạnh hoặc rót nóng lên ly đầy đá.

---

## Phần 10 — Hướng dẫn sức khỏe & lối sống

> **Cảnh báo phạm vi:** đây là hướng dẫn sản phẩm dựa trên KB của cửa hàng, không phải tư vấn y khoa.

### 10.1 Khách nói khó ngủ / mất ngủ

Đây là hướng dẫn quan trọng nhất trong tài liệu vì là câu hỏi phổ biến nhất. Ưu tiên theo thứ tự:
1. **Chamomile** — caffeine-free, gắn liền với việc thư giãn trước khi ngủ.
2. **Mugicha** hoặc **Sả–gừng** — caffeine-free, thay thế nếu khách không thích vị hoa cúc.
3. **Peppermint** — caffeine-free, tươi sáng hơn chamomile.
4. Nếu khách muốn vị "trà lá thật" và không quá nhạy cảm (chấp nhận một lượng nhỏ caffeine): **Hojicha** (10–20mg) hoặc **Genmaicha** (15–25mg) là lựa chọn hợp lý ở mức vừa phải.

**Không bao giờ khuyến nghị** gyokuro, matcha ceremonial, matcha culinary, sencha, oolong hoặc trà đen cho khách đã nói caffeine ảnh hưởng giấc ngủ.

### 10.2 "Matcha có ít caffeine hơn cà phê không?"

Theo KB: ceremonial matcha ~60–80mg tương đương một shot espresso (~60–80mg) và hơi thấp hơn một tách cà phê drip 240ml (~95mg). Vì vậy **không nên gọi matcha là "đồ uống ít caffeine"** một cách tuyệt đối. Sự khác biệt cảm nhận chủ yếu đến từ L-theanine (mục 2.8) — làm mượt đường cong caffeine chứ không giảm tổng lượng. Nếu khách thực sự muốn giảm caffeine so với cà phê, ưu tiên sencha, oolong, genmaicha, hoặc hojicha thay vì matcha.

### 10.3 Khách đang mang thai

Nhóm trà thảo mộc caffeine-free (chamomile, peppermint, sả-gừng, mugicha) luôn an toàn về mặt caffeine. Với trà lá, khách nên tự theo giới hạn caffeine của bác sĩ mình (hướng dẫn chung phổ biến là dưới khoảng 200mg/ngày từ mọi nguồn, nhưng bot không nên phát biểu điều này như tư vấn y khoa — chỉ nêu số liệu caffeine trong Phần 3 và để khách hỏi bác sĩ về giới hạn cụ thể). Một số nguồn khuyên hạn chế chamomile với lượng lớn khi mang thai — bot **không tự khẳng định** chamomile an toàn tuyệt đối trong thai kỳ; nếu khách muốn tránh câu hỏi này hoàn toàn, có thể chọn peppermint, sả-gừng hoặc mugicha vì đều 0mg caffeine và không có tranh cãi tương tự.

### 10.4 Đồ uống cho trẻ em

Ưu tiên nhóm thảo mộc không caffeine. **Không dùng mật ong cho trẻ dưới 1 tuổi** (nguy cơ infant botulism) — dùng syrup đường thay thế.

### 10.5 "Tôi uống cà phê bị jittery, trà có khác không?"

Giải thích hiệu ứng L-theanine (mục 2.8): caffeine của trà (đặc biệt matcha) thường tạo cảm giác tỉnh táo ổn định, ít đỉnh nhọn hơn cà phê — vì sao nhiều người jittery với cà phê lại thấy ổn với matcha/trà xanh. Tuy nhiên điều này khác nhau ở từng người — nếu khách nói họ nhạy cảm với **caffeine nói chung** (không riêng cà phê), nên chuyển hướng sang hojicha, genmaicha, hoặc trà thảo mộc không caffeine thay vì giả định matcha sẽ ổn với họ.

### 10.6 Khách hỏi đồ uống cho dạ dày khó chịu

Peppermint là lựa chọn tiêu chuẩn của shop cho việc dịu dạ dày. Gừng trong Lemongrass-Ginger cũng thường được liên hệ với việc giảm cảm giác buồn nôn. Không biến thông tin này thành lời hứa điều trị bệnh.

### 10.7 Khách muốn giảm caffeine

Hai lựa chọn "chuyển tiếp" phổ biến nhất: **Hojicha** (caffeine thấp) và **Mugicha** (0 caffeine) — cả hai có profile rang/toasty phù hợp với khách đang nhớ hương vị cà phê hoặc trà rang.

### 10.8 Khách muốn tăng năng lượng/tập trung

Matcha (ceremonial hoặc culinary) là lựa chọn tiêu chuẩn nhờ kết hợp caffeine + L-theanine mang lại sự tỉnh táo bền vững, ít crash hơn cà phê với một số người. Khuyến nghị dùng vào buổi sáng hoặc đầu giờ chiều, tham chiếu mức caffeine ở Phần 3.

---

## Phần 11 — Menu công thức & tùy chỉnh đầy đủ

Mỗi món dưới đây có thể tùy chỉnh theo các tiêu chí sau, trừ khi có ghi chú khác:

- **Mức đường:** 0%, 25%, 50%, 75%, 100% (100% = độ ngọt tiêu chuẩn).
- **Mức đá:** không đá, ít đá, đá bình thường (không áp dụng cho món nóng).
- **Loại sữa** (món có sữa): sữa bò nguyên kem, sữa yến mạch (oat), sữa đậu nành (soy), hoặc sữa hạnh nhân (almond) — xem Phần 12 về dị ứng.

### 11.1 Matcha Latte — Nóng
Caffeine: 40–60mg · Thời điểm phù hợp: sáng đến đầu giờ chiều.
Xem công thức chi tiết ở mục 4.2.

### 11.2 Matcha Latte — Đá
Caffeine: 40–60mg · Thời điểm phù hợp: bất kỳ lúc nào.
Xem công thức chi tiết ở mục 4.2.

### 11.3 Matcha Ceremonial — Nóng, uống nguyên chất
Caffeine: 60–80mg · Thời điểm phù hợp: sáng đến đầu giờ chiều. Không tùy chỉnh đường/sữa.
Xem công thức Usucha ở mục 4.1.

### 11.4 Genmaicha-Matcha Latte — Nóng/Đá
Caffeine: 20–35mg · Thời điểm phù hợp: chiều/tối cho khách muốn hương matcha nhưng ít caffeine hơn.
Xem công thức ở mục 4.3.

### 11.5 Hojicha Latte — Nóng
Caffeine: 10–20mg · Thời điểm phù hợp: bất kỳ lúc nào, kể cả buổi tối.
Xem công thức ở mục 6.1.

### 11.6 Hojicha Latte — Đá
Caffeine: 10–20mg · Thời điểm phù hợp: bất kỳ lúc nào.
Xem công thức ở mục 6.1.

### 11.7 Sencha — Nóng
Caffeine: 25–40mg · Thời điểm phù hợp: bất kỳ lúc nào, tốt nhất sáng/giữa trưa.
Xem công thức ở mục 5.1.

### 11.8 Sencha — Đá
Caffeine: 25–40mg · Thời điểm phù hợp: bất kỳ lúc nào.
Xem công thức ở mục 5.1.

### 11.9 Gyokuro — Nóng, uống nguyên chất
Caffeine: 70–90mg · Chỉ nên uống buổi sáng do caffeine cao. **Không có bản đá** theo menu chuẩn.
Xem công thức ở mục 5.2.

### 11.10 Trà Sữa Oolong — Nóng/Đá
Caffeine: 25–45mg · Thời điểm phù hợp: bất kỳ lúc nào.
Xem công thức ở mục 7.2.

### 11.11 Trà Sữa Đen (Black Milk Tea) — Nóng/Đá
Caffeine: 40–70mg · Thời điểm phù hợp: bất kỳ lúc nào.
Xem công thức ở mục 8.1.

### 11.12 Trà Hoa Cúc (Chamomile) — Nóng/Đá
Caffeine: 0mg · Thời điểm phù hợp: buổi tối/trước khi ngủ — món khuyên hàng đầu cho khách dễ mất ngủ (Phần 10.1).
Xem công thức ở mục 9.1.

### 11.13 Trà Bạc Hà (Peppermint) — Nóng/Đá
Caffeine: 0mg · Thời điểm phù hợp: bất kỳ lúc nào, đặc biệt mùa nóng khi pha đá.
Xem công thức ở mục 9.2.

### 11.14 Trà Sả Gừng (Lemongrass-Ginger) — Nóng/Đá
Caffeine: 0mg · Thời điểm phù hợp: bất kỳ lúc nào, được ưa chuộng mùa lạnh (nóng) và mùa nóng (đá).
Xem công thức ở mục 9.3.

### 11.15 Trà Lúa Mạch Rang (Mugicha) — Nóng/Đá
Caffeine: 0mg · Thời điểm phù hợp: bất kỳ lúc nào kể cả buổi tối; câu trả lời chuẩn cho "vị như hojicha nhưng không caffeine".
Xem công thức ở mục 9.4.

### 11.16 Theo mùa: Matcha Chanh Đá (Iced Matcha Lemonade)
Matcha culinary đánh vào nền nước chanh (nước cốt chanh tươi, syrup đường, nước lọc), phục vụ với đá. Caffeine ở mức trung bình, hơi thấp hơn matcha latte thường vì tỉ lệ matcha thấp hơn so với lượng nước. Món giải khát mùa nóng cho khách thích hương matcha nhưng muốn thứ nhẹ hơn latte có sữa — cũng là gợi ý khi khách muốn matcha ceremonial ở dạng đá (vì ceremonial truyền thống chỉ phục vụ nóng).

### 11.17 Theo mùa: Hojicha Affogato
Nước cốt hojicha nóng rưới trực tiếp lên 1 viên kem vani ngay tại bàn. Caffeine thấp. Món kết hợp tráng miệng và đồ uống, được ưa chuộng trong menu theo mùa thu/đông.

---

## Phần 12 — Dị ứng & chế độ ăn

- **Dairy:** sữa bò nguyên kem là mặc định cho đồ uống có sữa (matcha, hojicha, genmaicha-matcha latte, trà sữa oolong/đen). Oat, soy, almond là các lựa chọn thay thế cho khách dị ứng sữa/không dung nạp lactose/thuần chay.
- **Soy:** soy milk là lựa chọn thay thế nhưng bản thân đậu nành **là một allergen** — nếu khách nói có dị ứng nhưng chưa xác định allergen cụ thể, **không tự động chọn soy milk**.
- **Nuts:** almond milk chứa tree nuts. Khách dị ứng hạt **không nên** được tư vấn almond milk — cân nhắc oat hoặc soy milk nếu phù hợp.
- **Honey:** dùng làm sweetener tùy chọn cho chamomile. **Không dùng mật ong cho trẻ dưới 1 tuổi** (nguy cơ infant botulism) — dùng syrup đường thay thế.
- **Gluten:** trà, matcha và các nguyên liệu herbal trong tài liệu này đều naturally gluten-free. Mugicha là đồ uống từ lúa mạch (grain-based), nhưng quá trình rang/hãm không đưa gluten vào nước — an toàn cho khách tránh gluten thông thường. Nếu khách celiac hoặc cực kỳ nhạy cảm hỏi về **cross-contamination tại thiết bị của cửa hàng**, KB này không đủ dữ liệu để trả lời: *"Thông tin về quy trình chống nhiễm chéo của thiết bị không nằm trong Knowledge Base. Vui lòng hỏi trực tiếp nhân viên cửa hàng."*
- **Caffeine sensitivity / bệnh lý đã nêu:** luôn tham chiếu bảng caffeine ở Phần 3 và hướng dẫn ở Phần 10; không bao giờ khẳng định một tuyên bố sức khỏe cụ thể vượt quá những gì được viết trong tài liệu này.

---

## Phần 13 — Thiết bị & kỹ thuật pha

- **Chasen (chổi tre):** dùng để đánh matcha (mục 4.1, 4.2). Kỹ thuật đúng là đánh nhanh theo chuyển động "W"/zig-zag, không khuấy vòng tròn — khuấy vòng tròn sẽ không tạo được lớp bọt đặc trưng và dễ để lại vón cục.
- **Nhiệt độ nước quan trọng hơn với trà tinh tế:** gyokuro và matcha ceremonial đều dùng nước mát hơn hẳn (50–80°C) so với hojicha hay trà đen (90–100°C). Trà tinh tế, mỏng manh dễ bị "cháy" và đắng gắt trong nước sôi; trà rang, mạnh mẽ như hojicha và trà đen chịu được — và đôi khi cần — nước nóng hơn.
- **Thời gian ngâm ảnh hưởng đến vị đắng nhiều hơn lượng lá:** ngâm quá lâu chiết ra nhiều tannin và làm trà đắng; ngâm quá ngắn thì chiết chưa đủ vị. Khi không chắc chắn, nên bắt đầu ở đầu thấp của khoảng thời gian ghi trong công thức và để khách điều chỉnh ở lần pha sau.
- **Pha đậm gấp đôi cho đồ uống đá:** vì đá sẽ làm loãng thành phẩm, hầu hết công thức trà/latte đá trong tài liệu này dùng lượng lá/bột gấp đôi (hoặc nước ít hơn) khi pha nền, trước khi rót lên đá, để vị không bị nhạt.

---

## Phần 14 — FAQ (Câu hỏi thường gặp)

**Q: Ceremonial và culinary matcha khác nhau thế nào?**
A: Ceremonial cao cấp hơn, ngọt tự nhiên hơn, thiết kế để uống nguyên chất với nước (mục 4.1). Culinary mạnh mẽ và hơi đắng hơn khi uống trơn — chính điều đó giúp nó chịu được sữa và đường trong latte (mục 4.2). Nếu khách chỉ nói "matcha latte", họ muốn loại culinary — đây là mặc định của shop cho mọi đồ uống matcha pha sữa.

**Q: Món nào nhiều caffeine nhất?**
A: Gyokuro, khoảng 70–90mg/khẩu phần — cao hơn cả matcha ceremonial. Xem bảng đầy đủ ở Phần 3.

**Q: Món nào ít caffeine nhưng vẫn là "trà lá thật"?**
A: Hojicha (10–20mg) và Genmaicha (15–25mg) là hai loại trà lá thấp caffeine nhất menu. Để có 0 caffeine, nhóm trà thảo mộc (Phần 9) là câu trả lời.

**Q: Có thể làm mọi món thành iced không?**
A: Gần như mọi món, ngoại lệ chính là Gyokuro theo menu chuẩn (mục 5.2). Ceremonial matcha cũng theo truyền thống phục vụ nóng/nguyên chất; nếu khách muốn matcha đá, có thể hướng đến Iced Matcha Lemonade (mục 11.16) như lựa chọn matcha đá của shop.

**Q: Tôi đã uống gì lần trước?**
A: Bot cần dùng hệ thống lịch sử/recommendation history của khách nếu có sẵn, và trả lời trực tiếp dựa trên đó — không được đoán dựa trên KB này (nằm ngoài phạm vi tài liệu này).

**Q: Shop có bubble tea/boba không?**
A: Không có trên menu hiện tại. Nếu được hỏi, nói rõ và đề xuất lựa chọn gần nhất thực sự có — ví dụ trà sữa (mục 8.1, 11.11) cho khách muốn trải nghiệm béo, ngọt tương tự nhưng không có trân châu.

**Q: Có decaf matcha không?**
A: Không — matcha nói chung không được shop cung cấp ở dạng khử caffeine. Với hương vị gần matcha nhưng 0 caffeine, gợi ý Mugicha (mục 9.4); với ít (không phải 0) caffeine, gợi ý Genmaicha-Matcha Blend (mục 4.3). Luôn nói rõ đây **không phải** decaf matcha thật sự.

**Q: Món nào phù hợp ngay trước khi ngủ?**
A: Chamomile là lựa chọn đầu tiên — xem đầy đủ ở Phần 10.1. Các lựa chọn 0 caffeine khác gồm Mugicha, Sả–gừng và Peppermint.

---

## Phần 15 — Ma trận tư vấn nhanh cho chatbot

| Nhu cầu của khách | Ưu tiên | Tránh/Thận trọng |
|---|---|---|
| Muốn matcha nguyên bản | Ceremonial Matcha | Matcha latte nếu muốn trải nghiệm thuần |
| Muốn matcha latte | Culinary Matcha | Ceremonial nếu khách muốn nhiều sữa/đường |
| Muốn matcha nhưng ít caffeine | Genmaicha-Matcha Blend | Matcha ceremonial/culinary nguyên chất |
| Muốn ít caffeine (vẫn là trà lá) | Hojicha, Genmaicha | Gyokuro, matcha, trà đen |
| Muốn 0 caffeine | Chamomile, Peppermint, Sả–Gừng, Mugicha | Tất cả trà lá có caffeine |
| Khó ngủ | Chamomile → Mugicha/Sả–Gừng → Peppermint | Gyokuro, matcha, trà đen |
| Muốn vị rang | Hojicha, Mugicha | Sencha nếu không thích grassy |
| Muốn floral | Light Oolong | Dark Oolong nếu muốn vị nhẹ |
| Muốn trà đậm | Black Tea, Dark Oolong | Herbal tea |
| Muốn thay cà phê nhưng giảm caffeine | Hojicha/Mugicha | Gyokuro |
| Muốn đồ uống lạnh | Iced Matcha Latte, Sencha, Hojicha Latte, herbal iced | Gyokuro |
| Dị ứng dairy | Oat/Soy/Almond tùy allergen | Whole milk |
| Dị ứng tree nuts | Oat hoặc Soy nếu an toàn | Almond milk |
| Trẻ em | Herbal caffeine-free | Matcha, green tea, oolong, black tea |
| Hỏi về thuốc/bệnh | Chỉ cung cấp dữ liệu KB + khuyến nghị hỏi bác sĩ | Kết luận y khoa thay bác sĩ |

### Bảng tóm tắt theo câu nói của khách

| Nếu khách nói... | Đề xuất chính |
|---|---|
| "Tôi muốn matcha chuẩn" | Ceremonial Matcha |
| "Tôi muốn matcha latte" | Culinary Matcha |
| "Tôi muốn matcha nhưng ít caffeine" | Genmaicha-Matcha Blend |
| "Tôi không dùng caffeine" | Chamomile / Peppermint / Sả–Gừng / Mugicha |
| "Tôi khó ngủ" | Chamomile |
| "Tôi muốn vị giống cà phê nhưng ít caffeine" | Hojicha |
| "Tôi muốn vị rang nhưng 0 caffeine" | Mugicha |
| "Tôi thích vị floral" | Light Oolong |
| "Tôi thích trà đậm" | Black Tea |
| "Tôi muốn trà xanh nhẹ" | Sencha |
| "Tôi muốn umami mạnh" | Gyokuro |
| "Tôi muốn đồ uống lạnh" | Iced Matcha Latte / Sencha / Hojicha Latte / Herbal Tea |
| "Tôi dị ứng sữa" | Oat/Soy/Almond sau khi kiểm tra allergen |
| "Tôi dị ứng hạt" | Ưu tiên Oat; tránh Almond |
| "Tôi hỏi về thuốc/bệnh" | Chỉ cung cấp dữ liệu KB + khuyến nghị hỏi bác sĩ |

### Quy trình quyết định đề xuất đồ uống (bước tuần tự)

1. **Kiểm tra caffeine:** 0 caffeine → herbal/Mugicha; muốn thấp → Hojicha/Genmaicha; không quan tâm → tiếp tục.
2. **Xác định profile vị:** grassy → Sencha/Matcha; umami → Gyokuro/Ceremonial; floral → Light Oolong; roasted → Hojicha/Mugicha/Dark Oolong; bold/malty → Black Tea; minty → Peppermint; citrus/spicy → Sả–Gừng.
3. **Xác định sữa:** creamy → Latte/Milk Tea; không sữa → tea nguyên chất/herbal; dairy-free → chọn milk substitute sau khi kiểm tra allergen.
4. **Xác định nhiệt độ:** hot → công thức nóng; iced → công thức đá; Gyokuro → chỉ hot theo menu chuẩn.
5. **Kiểm tra allergen** trước khi đề xuất sữa: dairy allergy → không whole milk; nut allergy → không almond milk; soy allergy → không soy milk; celiac/cross-contamination → KB không đủ dữ liệu về thiết bị cửa hàng.
6. **Kiểm tra thời điểm:** buổi tối + caffeine-sensitive → ưu tiên caffeine-free hoặc low-caffeine; buổi sáng + muốn tỉnh táo → matcha/gyokuro/black tea có thể phù hợp nếu khách không nhạy caffeine.

---

## Phần 16 — Quy tắc vận hành cho AI/RAG

### 16.1 Khi trả lời, bot nên

1. Xác định **ý định** của khách.
2. Xác định các ràng buộc quan trọng: caffeine, thời điểm uống, dị ứng, nóng/lạnh, sữa, vị yêu thích.
3. Tra cứu KB.
4. Chỉ sử dụng thông tin có trong KB.
5. Đưa ra tối đa vài lựa chọn phù hợp thay vì liệt kê toàn bộ menu.
6. Giải thích ngắn gọn lý do chọn món.
7. Nếu là câu hỏi sức khỏe cá nhân, thêm giới hạn phù hợp (khuyến nghị hỏi bác sĩ khi cần).

### 16.2 Không được hallucinate

Không tự tạo: món mới, thành phần mới, hàm lượng caffeine mới, lợi ích y khoa, nguồn gốc trà không có trong KB, tình trạng tồn kho, giá, chương trình khuyến mãi, lịch sử order. Nếu dữ liệu không có: *"Thông tin này chưa được ghi nhận trong Knowledge Base của cửa hàng."*

### 16.3 Không nhầm "caffeine-free" với "low-caffeine"

**Caffeine-free = 0mg theo KB:** Chamomile, Peppermint, Lemongrass-Ginger, Mugicha.
**Low-caffeine ≠ caffeine-free:** Hojicha (10–20mg), Genmaicha (15–25mg). Đây là phân biệt quan trọng khi trả lời khách nhạy caffeine.

### 16.4 Không nhầm loại matcha

| Khái niệm | Ý nghĩa |
|---|---|
| Ceremonial matcha | Uống nguyên chất, vị tinh tế, thu hoạch đầu vụ |
| Culinary matcha | Phù hợp latte/đá/nấu ăn, thu hoạch sau |
| Genmaicha-Matcha | Blend matcha + gạo rang, caffeine thấp hơn |
| Decaf matcha | **Không có trong menu** |

### 16.5 Khi không đủ thông tin

Nếu câu hỏi yêu cầu thông tin ngoài KB: không đoán, nêu rõ giới hạn dữ liệu, đề nghị khách hỏi nhân viên hoặc cung cấp thêm thông tin nếu câu hỏi thuộc phạm vi tư vấn.

### 16.6 Checklist kiểm soát chất lượng câu trả lời

Trước khi gửi câu trả lời, bot nên tự kiểm tra:

- [ ] Thông tin có nằm trong KB không?
- [ ] Có vô tình tạo ra sản phẩm/thành phần không tồn tại không?
- [ ] Có phân biệt low-caffeine và caffeine-free không?
- [ ] Nếu khách nói mất ngủ, có tránh các món caffeine cao không?
- [ ] Nếu khách nói dị ứng, có kiểm tra allergen của loại sữa không?
- [ ] Có gọi thông tin sản phẩm là "điều trị", "chữa", "an toàn tuyệt đối" không?
- [ ] Có biến thông tin chung thành lời khuyên y khoa cá nhân không?
- [ ] Có nhầm ceremonial matcha với culinary matcha không?
- [ ] Có nhầm Mugicha là trà lá không (nó là lúa mạch, không phải trà)?
- [ ] Có tự đoán giá, tồn kho hoặc lịch sử order không?
- [ ] Nếu thông tin không có, có nói rõ giới hạn thay vì hallucinate không?

---

## Phần 17 — Ví dụ hội thoại chuẩn

**Khách:** "Tối nay tôi muốn uống trà nhưng sợ mất ngủ."
**Nên trả lời:** "Bạn nên ưu tiên Chamomile, Mugicha, Peppermint hoặc Sả-Gừng vì các món này không có caffeine theo thông tin của shop. Nếu bạn vẫn muốn trà lá, Hojicha là lựa chọn caffeine thấp khoảng 10–20mg mỗi khẩu phần."

**Khách:** "Tôi muốn matcha nhưng ít caffeine."
**Nên trả lời:** "Matcha vẫn chứa caffeine khá đáng kể. Nếu bạn muốn giữ một phần hương vị matcha nhưng giảm caffeine, Genmaicha-Matcha Blend là lựa chọn phù hợp hơn với khoảng 20–35mg. Nếu cần 0 caffeine, Mugicha là lựa chọn thay thế nhưng không phải matcha."

**Khách:** "Tôi dị ứng hạt, cho tôi almond milk."
**Nên trả lời:** "Almond milk chứa tree nuts nên không phù hợp nếu bạn có dị ứng với các loại hạt. Bạn có thể cân nhắc oat milk; soy milk cũng có sẵn nhưng bản thân đậu nành là một allergen."

**Khách:** "Có decaf matcha không?"
**Nên trả lời:** "Shop hiện không có matcha decaf. Nếu bạn muốn hương vị rang gần với matcha/tea nhưng không caffeine, Mugicha là lựa chọn 0 caffeine; nếu muốn vẫn có một chút matcha thì Genmaicha-Matcha Blend có khoảng 20–35mg."

---

## Phần 18 — Nguyên tắc cuối cùng

**Không có đồ uống "tốt nhất" cho mọi người — chỉ có đồ uống phù hợp nhất với nhu cầu của từng khách hàng.**

Chatbot cần ưu tiên theo thứ tự: **Đúng dữ liệu → Đúng nhu cầu → Đúng giới hạn tư vấn → Không hallucinate.**

---

*Tài liệu này mang tính tổng hợp thông tin tham khảo cho vận hành tư vấn của cửa hàng, không thay thế tư vấn y tế hoặc dinh dưỡng chuyên môn. Nếu khách có vấn đề sức khỏe, đang mang thai hoặc dùng thuốc có tương tác với caffeine, nên khuyến nghị họ tham khảo ý kiến bác sĩ.*

**Nguồn tổng hợp:** biên soạn nội bộ, một phần dựa trên các bài viết chuyên môn từ Uji Matcha Tea (ujimatchatea.com/blogs/news).
