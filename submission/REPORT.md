# Báo cáo Day 09 — Dương Quốc Huy, 2A202603311

## 1. Kết luận trước
**HOLD** (mã thoát 10). Lô vào **224 ảnh**; cửa vào loại **22** ảnh (hỏng/nhỏ/trùng/rò rỉ test), còn **202 ảnh** ra `submission/export/clean_v1/` (bản nháp, chưa phát hành).
Sau sửa tự động và 80 ảnh người duyệt: **0 lỗi bắt buộc**, nhưng **38/202 ảnh (18,8%)** còn cảnh báo chưa ai xem, ≥ ngưỡng 10% (`08_summary.json`).
Lý do gốc: hàng đợi người duyệt có **125 ảnh** > ngân sách **80 ảnh**.

## 2. Lỗi và phân việc
Số liệu `02_error_list_v1` (vòng 1, trên 224 ảnh; mã cấp ảnh tính trên 224, mã cấp dòng là số dòng / số ảnh).

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| DUP_IMAGE_EXACT | 8 ảnh | máy (loại ảnh) | md5 trùng từng byte: chắc chắn, không cần người |
| DUP_IMAGE_NEAR | 4 ảnh | máy (loại ảnh) | phash ≤ 12; cả 4 cặp đã mở xem đều là trùng thật (§3) |
| LEAK_TEST | 5 ảnh | máy (loại ảnh) | trùng ảnh test/val → giữ lại thì điểm test bị thổi phồng |
| CORRUPT_IMAGE / BAD_SIZE | 2 / 3 ảnh | máy (loại ảnh) | không mở được / cạnh ngắn < 250 px: quy tắc rõ |
| BAD_CLASS_NAME | 2 dòng (data.yaml: `Person`, `Bus`) | máy (`rename_classes`) | tên lớp chuẩn đã có trong config |
| BAD_FORMAT / BAD_CLASS_ID / BOX_ZERO / DUP_BOX | 3 / 6 / 4 / 7 dòng | máy (`drop_line`, 20 dòng) | dòng vô nghĩa, không thể đoán lại → xoá an toàn |
| BOX_OUT_OF_IMAGE | 8 dòng | máy (`clip_box`, 8 dòng) | cắt về [0,1] giữ lớp; phần trong ảnh vẫn đúng |
| MISSING_LABEL_FILE | 6 ảnh | **người** (`needs_label`) | máy không bịa nhãn; không tạo file rỗng (rỗng = ảnh nền) |
| POSSIBLE_MISSING | 53 cờ / 52 ảnh | **người** | model lớn thấy vật mà nhãn không có — có thể model sai |
| POSSIBLE_FALSE_POS | 29 cờ / 27 ảnh | **người** | box nhãn không khớp vật nào model thấy (precision calib chỉ 0,31) |
| POSSIBLE_LOOSE_BOX | 28 cờ / 24 ảnh | **người** | đúng vật, box lệch: cần mắt người chỉnh |
| POSSIBLE_WRONG_CLASS | 18 cờ / 18 ảnh | **người** | nhầm lớp hợp lệ (truck↔car…): quy tắc cú pháp không bắt được |
| EMPTY_LABEL / BOX_TINY / BOX_HUGE | 12 / 6 / 3 | **người** | có thể đúng (ảnh nền, vật nhỏ/to thật) → chỉ cảnh báo |

Tổng: 36 lỗi bắt buộc + 153 cảnh báo ở vòng 1 → `03_fixes.csv` ghi **35 thay đổi** (20 drop_line, 8 clip_box, 6 needs_label, 1 rename_classes) → vòng 2 còn đúng **6 lỗi bắt buộc** (6 ảnh thiếu nhãn) và cảnh báo trên **112/202 ảnh**.
Chú ý: autofix xoá hết dòng của 3 file (img_0050, img_0104, img_0194) nên EMPTY_LABEL tăng 12 → 15: các ảnh này phải vào tay người, không coi là "ảnh nền".

**Hàng đợi** (`05_review_queue.csv`, 125 ảnh): điểm = Σ trọng số mã × (1 + conf của model) + điểm cho dòng đã bị máy sửa. 6 ảnh `NEEDS_LABEL` (trọng số 10) lên đầu vì chưa có nhãn là lỗi bắt buộc, không duyệt thì không bao giờ Release; đứng đầu là img_0020 (11,5: FIXED_DROP_LINE + MISSING + WRONG_CLASS). Sau đó là ảnh nhiều cờ ngữ nghĩa có conf cao (WRONG_CLASS 3, MISSING/FALSE_POS 2).
**Với ngân sách 80 ảnh**: người duyệt 74/103 ảnh có cờ ngữ nghĩa (94/123 cờ POSSIBLE_*); cờ ngữ nghĩa giảm 123 → 57. 38 ảnh còn cảnh báo chưa xem chủ yếu là LOOSE_BOX (16), FALSE_POS (11), BOX_TINY (6) — đúng loại ưu tiên thấp.

## 3. Calibration (2 ngưỡng)
Bộ calib 39 ảnh, `submission/calibration/calibration_report.md`.

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **12** | NEAR: 1,00/0,50 → **1,00/0,67** (EXACT giữ 1,00/1,00) | Loại ảnh là hành động **tự động, không hoàn tác** → precision quan trọng hơn recall. 4–14 cùng P/R trên calib; 12 nằm giữa vùng phẳng, trên raw không thêm ảnh oan (xem dưới). |
| `second_opinion.conf` | 0,25 | **0,6** | WRONG_CLASS 0,56/0,83 → **0,62/0,83**; MISSING 0,50/1,00 → **0,57/1,00**; LOOSE_BOX 0,29/0,40 → 0,20/0,20; FALSE_POS 0,31/1,00 (không đổi, dùng `fp_conf`) | Cảnh báo chỉ chuyển người nên giữ recall: 0,6 là giá trị **cao nhất vẫn giữ recall MISSING = 1,00 và WRONG_CLASS = 0,83**, đồng thời bớt FP (cảnh báo raw 271 → 153, hàng đợi 143 → 125). Cái giá: LOOSE_BOX recall giảm. |

**Chỗ calibration có thể đánh lừa — `phash_dist`:** trên calib, 16 cho NEAR tốt nhất (1,00/**0,83**) mà precision vẫn 1,00. Nhưng calib chỉ 39 ảnh nên rất ít cặp ảnh *khác nhau* để lộ báo động giả. Chạy `duplicates` trên raw:

| phash_dist | EXACT | LEAK_TEST | NEAR | tổng loại |
|---|---:|---:|---:|---:|
| 2–4 | 8 | 4 | 2 | 14 |
| 6–8 | 8 | 5 | 3 | 16 |
| **10–14** | 8 | 5 | 4 | **17** |
| 16 | 8 | 11 | 7 | 26 |
| 20 | 4 | 105 | 25 | 134 |

Mở xem từng cặp mới: ở 6 và 10 (img_0223~img_0077, img_0101~test_039 có viền đen, img_0186~img_0061) đều là trùng thật. Ở 16 thêm 9 ảnh nhưng chỉ img_0084~img_0074 là trùng thật; còn lại là ảnh khác hẳn (img_0011 tennis ~ img_0008 trượt tuyết, img_0177 lướt sóng ~ img_0113 chân dung, img_0013 bàn làm việc ~ test_087 bóng chày…) → tin calib sẽ xoá oan ~8 ảnh tốt và ghi sai "rò rỉ test". Ở 20, 134/224 ảnh bị loại.
Tương tự với `conf`: 0,8 cho **Release** (16/202 = 7,9%) nhưng recall MISSING tụt 1,00 → 0,75 — đó là "Release giả" do hạ recall cho hàng đợi vừa ngân sách, nên không chọn.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Gate chặn đúng.** `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`:
```
kết luận: REWORK — còn 6 lỗi bắt buộc (ERROR) chưa sửa -> phải làm lại trước khi phát hành
Bước 5/5  KHÔNG xuất: còn lỗi bắt buộc (Rework) — trả về bước 3
exit=20     ls work/exp_nb -> No such file or directory
```
6 lỗi đó là 6 ảnh MISSING_LABEL_FILE: không có người thì không ai gán nhãn, và gate không cho xuất. Với ngân sách 80 thì ra Hold (mã 10), xuất bản nháp có ghi `decision: Hold` trong `manifest.json`.

**(b) Điểm mù (có bằng chứng):**
1. **Ảnh trùng biến đổi mạnh vượt `phash_dist`.** img_0084 và img_0074 là cùng một cảnh (đã mở xem), khoảng cách phash 16 > 12 nên **cả hai vẫn nằm trong clean_v1**. Calib cũng còn 2/6 ảnh NEAR bị sót (recall 0,67).
2. **Box lỏng nhẹ gần như không bị bắt.** LOOSE_BOX trên calib chỉ P/R = 0,20/0,20 (1/5 lỗi chèn). Box lệch mà IoU với dự đoán vẫn ≥ 0,5 thì không bị cờ; và 16 ảnh LOOSE_BOX còn lại nằm ngoài ngân sách duyệt.
3. **Model lớn cũng nhầm / mơ hồ lớp.** Sau khi người duyệt thay bằng nhãn người, 25 ảnh vẫn bị second_opinion cờ (11 MISSING, 10 FALSE_POS, 3 WRONG_CLASS). Ví dụ img_0083: xe nhỏ ở xa, nhãn người là bus, model nói car (conf 0,69, IoU 0,97); img_0078: nhãn người khác lớp, model nói car (IoU 0,92). Nghĩa là nhầm lớp mà chính model cũng nhầm thì cờ này không đáng tin, và lỗi nhầm lớp thật mà model đồng ý với nhãn sai sẽ lọt hoàn toàn (WRONG_CLASS calib còn 1/6 FN).

Lỗi tự nhìn thấy trên `work/viz/`: img_0078 có xe trắng bên trái không có box (máy cũng cờ POSSIBLE_MISSING, conf 0,85) và box xe sát mép phải tràn 0,03 (đã clip); img_0083 xe nhỏ ở xa gán "bus" khó xác định; img_0084/img_0074 là ảnh trùng không bị loại.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Colab T4, `scripts/train_compare.py`: `yolo26n.pt`, 20 epoch, imgsz 640, batch 16, seed 0 và 1. Hai biến thể dùng cùng val (gold_val, 40 ảnh) và cùng test (100 ảnh nhãn người), chỉ khác dữ liệu train. `manifest_sha1`/`config_sha1` trong `results/*.json` khớp bản export và config đã nộp (`check_submission.py` không báo lỗi phần train).

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 202 | 2 | 0.701 ± 0.025 | 0.487 ± 0.008 | 0.759 ± 0.003 | 0.625 ± 0.019 |

**Chênh mAP50 (clean − raw) = −0,025**, xấp xỉ **1 lần độ lệch giữa 2 seed của clean** (0,025). Từng seed: raw 0,7256 / 0,7259, clean 0,718 / 0,683, nên seed tốt của clean gần bằng raw. mAP50-95 chênh −0,024, lớn hơn độ lệch seed (0,004–0,008), nghĩa là raw nhỉnh hơn một chút về độ khít box.
**Kết luận trung thực:** dữ liệu **không** cho thấy clean tốt hơn raw. Trên mAP50, chênh lệch nằm trong mức nhiễu nên chưa kết luận được chiều nào. Chỉ có 2 seed nên chính độ lệch chuẩn cũng ước lượng rất thô (độ lệch 0,000 của raw là do may mắn, không có nghĩa raw ổn định).

AP50 theo lớp (TB 2 seed, raw → clean): car 0,738 → 0,738; person 0,822 → 0,823; bus 0,695 → 0,703; **truck 0,648 → 0,538**. Toàn bộ khoảng chênh đến từ lớp truck, mà chính truck của clean cũng dao động 0,590 / 0,486 giữa 2 seed.

**Giả thuyết và cách kiểm:**
1. **Raw được "cộng điểm" nhờ rò rỉ test.** Raw còn 5 ảnh trùng tập test (LEAK_TEST: test_009/033/039/044/085), thêm 8 ảnh trùng từng byte và 4 ảnh gần trùng. Model raw đã "thấy" 5/100 ảnh test lúc train nên điểm test bị thổi phồng. *Kiểm:* chấm lại cả hai model trên 95 ảnh test còn lại (bỏ 5 ảnh rò rỉ), rồi so lại chênh lệch.
2. **Ultralytics tự "làm sạch cú pháp" cho raw.** Log train của raw cảnh báo đủ loại: ảnh hỏng/cắt cụt, box tràn ảnh, class ID lạ, giá trị âm, sai số cột. Ultralytics tự bỏ các ảnh/nhãn này, nên raw thực ra không bẩn như con số 224 ảnh gợi ý. Phần pipeline đóng góp thêm chủ yếu là sửa ngữ nghĩa (80 ảnh người duyệt) và loại 22 ảnh. *Kiểm:* đếm số ảnh Ultralytics thực sự giữ lại cho raw trong log (lần chạy này em không lưu con số cụ thể) và lặp lại thí nghiệm với raw đã bỏ các ảnh hỏng.
3. **Clean trộn hai quy ước car/truck.** Số box: raw có car 121 / truck 32, clean có car 101 / truck 41. 80 ảnh người duyệt được thay bằng nhãn người (chuyển một phần car → truck), 122 ảnh còn lại giữ cách gán của người gán ban đầu. Cùng một kiểu xe (bán tải, SUV) có ảnh gán car, có ảnh gán truck; check thưởng `class_conflict` còn thấy 2 vật bị gán cả hai lớp (img_0037, img_0153). Model nhỏ học 20 epoch sẽ bị nhiễu ở đúng lớp truck. *Kiểm:* train biến thể `oracle` (nhãn người toàn bộ) và so AP truck; hoặc duyệt hết hàng đợi để mọi ảnh dùng cùng một quy ước.
4. **Test nhỏ, lớp truck ít mẫu.** Với 100 ảnh test, vài box truck đổi kết quả là AP truck dao động ±0,05 giữa các seed. *Kiểm:* chạy ≥ 5 seed và báo khoảng tin cậy.

**Việc tiếp theo:** duyệt hết hàng đợi (Release), loại img_0084 và 2 ca `class_conflict`, chấm lại trên test bỏ 5 ảnh rò rỉ, chạy ≥ 5 seed và thêm `oracle` làm chặn trên. Chỉ khi chênh lệch vượt độ lệch giữa các seed mới kết luận dữ liệu sạch giúp model tốt hơn.

## 6. Quyết định và ghi chú AI
**(a) Quyết định: HOLD.** Không phát hành clean_v1. Để thành Release cần: người duyệt thêm ít nhất **18 ảnh** trong 38 ảnh còn cảnh báo (để còn ≤ 20/202 < 10%), ưu tiên theo `05_review_queue.csv`; tăng ngân sách duyệt là quyết định của dự án, không phải hạ `conf`. Đồng thời nên loại tay img_0084 (trùng img_0074) trước khi train.

**(b) Dùng AI (Claude Code):**
- *Prompt chính:* "viết 4 module" — AI đọc docstring stub (đầu vào/đầu ra, bảng mã lỗi, ngưỡng trong `cfg`) và toàn bộ file test làm ca biên, rồi viết code; không đụng file "ĐÃ VIẾT SẴN"/`tests/`/`data/`.
- *Cách kiểm:* `pytest` 79/79 xanh; tự chạy thêm 3 ca khó (một dòng tràn + trùng → chỉ 1 `drop_line`; dòng trống giữa file giữ số dòng gốc; nhiều dự đoán trên một ảnh, chạy autofix lần 2 không đổi gì); sweep calib trùng khớp bảng mẫu của đề; đọc lại từng dòng.
- *1 lần AI sai:* (thêm) test thưởng đầu tiên đặt ngưỡng IoU = 1.0 cho hai box giống hệt nhau và fail vì sai số float; sửa test sang cặp box có IoU tính tay ≈ 0,818. Và khi viết `gate.py`, AI sinh một dòng nháp sai cú pháp (`def decide(...) if False else None`) trong script ghi file; phát hiện trước khi ghi đè, viết lại hàm bằng Edit và chạy `test_gate.py` để xác nhận.

## Thưởng: check mới `class_conflict` (một vật hai lớp)
`pipeline/checks/class_conflict.py` + `tests/test_class_conflict.py` (6 test: báo ở dòng sau, cùng lớp để cho DUP_BOX, chồng một phần thì im, ngưỡng đọc từ cfg + mặc định, dòng hỏng/trống giữ số dòng, 3 lớp trên một vật). `DUP_BOX` chỉ bắt box lặp **cùng lớp**; check này cảnh báo (WARN, không tự xoá) khi hai box **khác lớp** có IoU > 0,8.
Chạy riêng vì registry check và config đã ghim: `python -m pipeline.checks.class_conflict work/run/ds --out submission/extra/class_conflict_clean.csv`.

Kết quả: **2/224 ảnh raw**, và cả 2 **vẫn còn trong clean_v1** (pipeline chính không bắt): img_0037 dòng 9 truck trùng car dòng 8 (IoU 0,98, chiếc bán tải giữa ảnh), img_0153 dòng 6 truck trùng bus dòng 3 (IoU 0,97, xe ở xa). Số ảnh bị cờ không đổi với mọi ngưỡng 0,6–0,9, nên ngưỡng không nhạy. gold_val (nhãn người) cũng có 1 ca (car+truck, IoU 1,0) → đây là nhãn mơ hồ có thật trong COCO, đúng là việc của người quyết, nên chỉ cảnh báo.
