"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_CODES = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _is_remove(code):
    return code in REMOVE_CODES or code.startswith("DUP_IMAGE_")


def _remove_image(ds, stem):
    """Xoá mọi ảnh có stem này + file nhãn. Trả về tên các file đã xoá (rỗng nếu không còn gì để xoá)."""
    gone = []
    for p in ds.image_files():
        if p.stem == stem:
            p.unlink()
            gone.append(p.name)
    lp = ds.label_path(stem)
    if lp.exists():
        lp.unlink()
        gone.append(lp.name)
    return gone


def _clip(text):
    """Cắt box về [0,1]. Trả về dòng mới, hoặc None nếu sau khi cắt box không còn diện tích."""
    c, x, y, w, h = parse_yolo_line(text)
    x1, y1 = max(0.0, x - w / 2), max(0.0, y - h / 2)
    x2, y2 = min(1.0, x + w / 2), min(1.0, y + h / 2)
    if x2 <= x1 or y2 <= y1:
        return None
    return f"{c} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}"


def fix(ds, issues, cfg):
    fixes = []
    errors = [i for i in issues if i.severity == ERROR]      # WARN là việc của người, không động tới

    # 1) Xoá ảnh trước: issue dòng của ảnh đã xoá sẽ được bỏ qua êm ở bước 3.
    removed = set()
    for i in errors:
        if _is_remove(i.code) and i.image not in removed:
            removed.add(i.image)
            gone = _remove_image(ds, i.image)
            if gone:                                          # đã xoá ở lần chạy trước -> không ghi gì (idempotent)
                fixes.append({"image": i.image, "line": None, "action": "remove_image",
                              "before": ", ".join(gone), "after": f"(đã xoá: {i.code})"})

    # 2) Lỗi cấp ảnh / dataset.
    renamed = False
    for i in errors:
        if i.code == "MISSING_LABEL_FILE" and i.image not in removed:
            # Không tạo file nhãn (rỗng = "ảnh nền"): đẩy cho người gán.
            fixes.append({"image": i.image, "line": None, "action": "needs_label",
                          "before": "(không có file)", "after": "chuyển người gán"})
        elif i.code == "BAD_CLASS_NAME" and not renamed:
            renamed = True                                    # nhiều issue BAD_CLASS_NAME -> sửa data.yaml 1 lần
            d = (yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) if ds.yaml_path.exists() else None) or {}
            before = d.get("names")
            d["names"] = {k: n for k, n in enumerate(cfg["classes"])}
            ds.yaml_path.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
            fixes.append({"image": "data.yaml", "line": None, "action": "rename_classes",
                          "before": str(before), "after": str(list(cfg["classes"]))})

    # 3) Lỗi dòng: gom theo file (số dòng là số dòng GỐC), xoá thắng cắt, ghi lại file MỘT lần.
    drop, clip = defaultdict(set), defaultdict(set)
    for i in errors:
        if i.line is None or i.image in removed:
            continue
        if i.code in DROP_CODES:
            drop[i.image].add(i.line)
        elif i.code == "BOX_OUT_OF_IMAGE":
            clip[i.image].add(i.line)

    for stem in sorted(set(drop) | set(clip)):
        lp = ds.label_path(stem)
        if not lp.exists():
            continue
        raw = lp.read_text(encoding="utf-8", errors="replace").splitlines()   # giữ dòng trống -> số dòng không lệch
        out, changed = [], False
        for no, text in enumerate(raw, 1):
            if no in drop[stem]:
                fixes.append({"image": stem, "line": no, "action": "drop_line", "before": text, "after": ""})
                changed = True
                continue
            if no in clip[stem]:
                try:
                    new = _clip(text)
                except ValueError:                            # dòng hỏng mà chỉ bị báo tràn: an toàn nhất là xoá
                    new = None
                if new is None:
                    fixes.append({"image": stem, "line": no, "action": "drop_line", "before": text,
                                  "after": "(box nằm ngoài ảnh)"})
                    changed = True
                    continue
                if new != text:
                    fixes.append({"image": stem, "line": no, "action": "clip_box", "before": text, "after": new})
                    changed = True
                text = new
            out.append(text)
        if changed:
            lp.write_text("".join(t + "\n" for t in out), encoding="utf-8")
    return fixes
