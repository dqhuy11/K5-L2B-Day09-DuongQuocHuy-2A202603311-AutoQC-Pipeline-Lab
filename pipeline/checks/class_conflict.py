"""CHECK THÊM (thưởng) — Một vật bị gán HAI lớp: hai box KHÁC lớp chồng khít lên nhau.

`label_format` chỉ bắt DUP_BOX khi hai box CÙNG lớp. Nếu người gán vẽ cùng một chiếc xe hai lần, một lần "car"
một lần "truck", thì không quy tắc cú pháp nào báo, và model train sẽ học hai đáp án mâu thuẫn cho cùng một vật.

| code           | severity | khi nào                                                                          |
|----------------|----------|----------------------------------------------------------------------------------|
| CLASS_CONFLICT | WARN     | box khác lớp với một dòng TRƯỚC ĐÓ và IoU > `iou` (mặc định 0.8); báo ở dòng SAU |

Chỉ CẢNH BÁO (không tự xoá): máy không biết lớp nào đúng; có ca hợp lệ hiếm (vd. COCO gán SUV cả car lẫn truck).
Ngưỡng đọc từ `cfg["class_conflict"]["iou"]` nếu có, không thì dùng DEFAULT_IOU (config dự án đã ghim nên không thêm khoá).
Trên lô raw kết quả như nhau với mọi ngưỡng 0.6–0.9 (2 ảnh, IoU 0.97–0.98), nên 0.8 không nhạy với lựa chọn.

Chạy riêng (không nằm trong registry đã ghim của pipeline):
    python -m pipeline.checks.class_conflict work/run/ds --out submission/extra/class_conflict.csv
"""
from __future__ import annotations

import argparse
import sys

from ..common import WARN, Issue, iou_xywh, load_config, parse_yolo_line, write_issues_csv, Dataset

DEFAULT_IOU = 0.8


def run(ds, cfg):
    th = (cfg.get("class_conflict") or {}).get("iou", DEFAULT_IOU)
    n_cls = len(ds.classes)
    issues = []
    for lp in ds.label_files():
        stem = lp.stem
        seen = []                                           # (số dòng, id, box) các dòng hợp lệ trước đó
        for no, text in ds.read_label_lines(stem) or []:
            try:
                c, x, y, w, h = parse_yolo_line(text)
            except ValueError:
                continue                                    # dòng hỏng: label_format báo
            if not 0 <= c < n_cls or w <= 0 or h <= 0:
                continue
            box = (x, y, w, h)
            # IoU cao nhất; hoà thì lấy dòng sớm nhất
            best = max(((iou_xywh(b, box), pno, pc) for pno, pc, b in seen if pc != c),
                       key=lambda t: (t[0], -t[1]), default=None)
            if best and best[0] > th:
                v, pno, pc = best
                issues.append(Issue("class_conflict", WARN, "CLASS_CONFLICT", stem,
                                    f"box {ds.classes[c]} trùng box {ds.classes[pc]} ở dòng {pno} (IoU {v:.2f}): một vật hai lớp?",
                                    no, {"iou": round(v, 4), "other_line": pno, "classes": [ds.classes[pc], ds.classes[c]]}))
            seen.append((no, c, box))
    return issues


def main(argv=None):
    ap = argparse.ArgumentParser(description="Tìm box khác lớp chồng khít nhau (một vật hai lớp).")
    ap.add_argument("dataset", help="thư mục dataset YOLO (images/, labels/)")
    ap.add_argument("--out", help="ghi CSV danh sách issue")
    ap.add_argument("--config", default=None)
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    issues = run(Dataset(a.dataset, cfg["classes"]), cfg)
    for i in issues:
        print(f"[{i.severity.upper()}] {i.code:15s} {i.image}  dòng {i.line}: {i.message}")
    print(f"{len(issues)} cảnh báo trên {len({i.image for i in issues})} ảnh")
    if a.out:
        write_issues_csv(issues, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
