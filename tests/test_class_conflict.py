"""Test cho check thưởng `class_conflict` (file mới của học viên, không thuộc bộ test đã ghim)."""
from pipeline.checks import class_conflict


def run(make_ds, cfg, lines):
    ds = make_ds(images={"a": 1}, labels={"a": lines})
    return [(i.code, i.line) for i in class_conflict.run(ds, cfg)]


def test_same_object_two_classes_is_flagged_on_later_line(make_ds, cfg):
    assert run(make_ds, cfg, ["0 0.5 0.5 0.3 0.4", "2 0.505 0.5 0.3 0.4"]) == [("CLASS_CONFLICT", 2)]


def test_same_class_overlap_is_left_to_dup_box(make_ds, cfg):
    assert run(make_ds, cfg, ["0 0.5 0.5 0.3 0.4", "0 0.5 0.5 0.3 0.4"]) == []


def test_partial_overlap_is_silent(make_ds, cfg):
    # person đứng cạnh car: IoU thấp -> hợp lệ
    assert run(make_ds, cfg, ["0 0.5 0.5 0.3 0.4", "1 0.6 0.5 0.1 0.3"]) == []


def test_threshold_from_config_and_boundary_is_strict(make_ds, cfg):
    lines = ["0 0.5 0.5 0.3 0.4", "2 0.53 0.5 0.3 0.4"]       # giao 0.27*0.4=0.108, hợp 0.132 -> IoU ≈ 0.818
    cfg["class_conflict"] = {"iou": 0.85}
    assert run(make_ds, cfg, lines) == []
    cfg["class_conflict"] = {"iou": 0.8}
    assert run(make_ds, cfg, lines) == [("CLASS_CONFLICT", 2)]
    del cfg["class_conflict"]                                   # không có khoá -> mặc định 0.8
    assert run(make_ds, cfg, lines) == [("CLASS_CONFLICT", 2)]


def test_bad_lines_and_blank_lines_do_not_crash_and_keep_line_numbers(make_ds, cfg):
    got = run(make_ds, cfg, ["0 0.5 0.5 0.3 0.4", "garbage", "", "93 0.5 0.5 0.3 0.4", "3 0.5 0.5 0.3 0.4"])
    assert got == [("CLASS_CONFLICT", 5)]


def test_three_classes_on_one_object_give_two_warnings_and_severity_is_warn(make_ds, cfg):
    ds = make_ds(images={"a": 1}, labels={"a": ["0 0.5 0.5 0.3 0.4", "2 0.5 0.5 0.3 0.4", "3 0.5 0.5 0.3 0.4"]})
    iss = class_conflict.run(ds, cfg)
    assert [(i.line, i.extra["other_line"]) for i in iss] == [(2, 1), (3, 1)]
    assert all(i.severity == "warn" for i in iss)
