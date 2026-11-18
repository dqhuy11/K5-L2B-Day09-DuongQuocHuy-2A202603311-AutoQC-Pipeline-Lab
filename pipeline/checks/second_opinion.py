"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401
from ..model_cache import get_preds  # noqa: F401


def _valid_lines(ds, stem):
    """[(số dòng gốc, (id, cx, cy, w, h))] của các dòng parse được và id lớp hợp lệ."""
    out = []
    for no, text in ds.read_label_lines(stem) or []:
        try:
            b = parse_yolo_line(text)
        except ValueError:
            continue
        if 0 <= b[0] < len(ds.classes):
            out.append((no, b))
    return out


def run(ds, cfg, preds=None):
    so = cfg["second_opinion"]
    conf, min_area, fp_conf = so["conf"], so["min_area_px"], so["fp_conf"]
    iou_missing, iou_match, iou_loose = so["iou_missing"], so["iou_match"], so["iou_loose"]
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    issues = []
    for p in ds.image_files():
        stem = p.stem
        if stem not in preds or ds.read_label_lines(stem) is None:
            continue
        rows = preds[stem] or []
        labels = _valid_lines(ds, stem)
        size = ds.image_size(stem)

        def add(code, msg, line=None, **extra):
            issues.append(Issue("second_opinion", WARN, code, stem, msg, line, extra))

        # (A) Từng dự đoán đủ tin cậy + đủ lớn: model thấy gì mà nhãn không khớp?
        for r in rows:
            rc, rconf, rbox = int(r[0]), float(r[1]), r[2:6]
            if rconf < conf:
                continue
            if size and rbox[2] * size[0] * rbox[3] * size[1] < min_area:
                continue
            cands = [(iou_xywh(rbox, b[1:]), b[0]) for _, b in labels]
            cands = [(v, c) for v, c in cands if v >= iou_missing]
            same = [v for v, c in cands if c == rc]
            other = [v for v, c in cands if c != rc]
            if not cands:
                add("POSSIBLE_MISSING", f"model thấy {ds.classes[rc]} (conf {rconf:.2f}) mà nhãn không có box",
                    conf=rconf, cls=rc, box=list(rbox))
            elif same:
                if max(same) < iou_loose:
                    add("POSSIBLE_LOOSE_BOX", f"box {ds.classes[rc]} lệch/lỏng: IoU {max(same):.2f} < {iou_loose}",
                        conf=rconf, iou=round(max(same), 4))
                # cùng lớp và đủ khít -> nhãn đã phủ vật này, không cờ
            elif max(other) >= iou_match:
                add("POSSIBLE_WRONG_CLASS", f"model nói {ds.classes[rc]} (conf {rconf:.2f}) nhưng nhãn khác lớp, IoU {max(other):.2f}",
                    conf=rconf, iou=round(max(other), 4), cls=rc)
            # chỉ có khác lớp với IoU trong [iou_missing, iou_match): mơ hồ -> im lặng

        # (B) Từng dòng nhãn: có khớp với BẤT KỲ dự đoán nào (conf >= fp_conf, không lọc diện tích) không?
        loose_preds = [r[2:6] for r in rows if float(r[1]) >= fp_conf]
        for no, b in labels:
            best = max((iou_xywh(b[1:], rb) for rb in loose_preds), default=0.0)
            if best < iou_missing:
                add("POSSIBLE_FALSE_POS", f"box {ds.classes[b[0]]} không khớp vật nào model thấy (IoU tốt nhất {best:.2f})",
                    no, iou=round(best, 4))
    return issues
