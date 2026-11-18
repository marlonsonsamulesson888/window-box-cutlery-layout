#!/usr/bin/env python3
"""开窗盒餐具排布计算（只算数和查规则，不出图、不判定合格）。

输入 JSON（见 examples/）：盒面尺寸、餐具清单（长度、最宽处宽度、竖向放法）、
间隙与规则默认值、可选的窗口宽度/窗沿轮廓/中心距锁定值。
输出：中心距、组宽、窗宽可行范围与建议、两侧留纸、每支的上下端位置、垫高、
压纸/露尾、头部离窗沿距离、贴膜尺寸，以及逐条规则检查（ok / warn / fail）。
仅标准库。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

DEFAULT_RULES = {
    "gap_mm": 6.0,                 # 相邻两支最宽处之间的净距
    "pitch_round_mm": 0.5,         # 中心距取整步长（四舍五入）
    "item_clearance_min_mm": 8.0,  # 组外包络到窗左右边最小净距
    "item_clearance_target_mm": 10.0,  # 建议窗宽用的净距
    "side_paper_min_mm": 10.0,     # 窗边到盒面左右折线最少留纸
    "head_below_window_top_mm": [5.0, 15.0],  # 头顶低于该列窗沿的建议范围
    "handle_end_margin_mm": 10.0,  # 柄尾要么在窗内且离窗底 ≥此值，要么压纸 ≥此值
    "decoration_from_fold_min_mm": 5.0,
    "film_overlap_mm": 10.0,       # 窗膜每边比窗大
    "film_to_fold_min_mm": 2.0,    # 窗膜边离折线最少
    "inner_corner_radius_min_mm": 1.5,
    "window_width_round_mm": 1.0,  # 建议窗宽向上取整步长
}


def rnd(v, step):
    return round(round(v / step) * step, 4) if step else v


def interp(profile, x):
    """窗沿轮廓：[[x_mm, top_mm], ...] 线性插值；超出两端取端点值。"""
    pts = sorted(profile)
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 != x0 else min(y0, y1)
    return pts[-1][1]


def status(ok, warn=False):
    return "ok" if ok else ("warn" if warn else "fail")


def compute(cfg):
    rules = dict(DEFAULT_RULES)
    rules.update(cfg.get("rules", {}))
    box = cfg["box"]
    W, H = float(box["width_mm"]), float(box["height_mm"])
    inner_bottom = float(box.get("inner_bottom_mm", H))
    items = cfg["items"]
    if len(items) < 1:
        raise ValueError("items 至少一支")
    gap = float(cfg.get("gap_mm", rules["gap_mm"]))
    widths = [float(i["max_width_mm"]) for i in items]
    checks = []

    # 1. 中心距
    pitches, notes = [], []
    locks = cfg.get("pitch_overrides", {})
    for k in range(len(items) - 1):
        calc = widths[k] / 2 + gap + widths[k + 1] / 2
        key = f"{items[k]['name']}-{items[k + 1]['name']}"
        p = rnd(calc, rules["pitch_round_mm"])
        if key in locks or str(k) in locks:
            lock = float(locks.get(key, locks.get(str(k))))
            notes.append({"pair": key, "calculated_mm": round(calc, 2), "locked_mm": lock})
            if lock < calc - 1e-6:
                checks.append({"rule": f"锁定中心距 {key}", "status": "fail",
                               "detail": f"锁定 {lock} < 计算最小 {calc:.2f}，最宽处净距不足 {gap}"})
            p = lock
        pitches.append(p)
    span = sum(pitches) + widths[0] / 2 + widths[-1] / 2

    # 2. 窗宽与留纸
    win_min = span + 2 * rules["item_clearance_min_mm"]
    win_max = W - 2 * rules["side_paper_min_mm"]
    step = rules["window_width_round_mm"]
    suggest = math.ceil((span + 2 * rules["item_clearance_target_mm"]) / step - 1e-9) * step
    suggest = min(max(suggest, math.ceil(win_min / step - 1e-9) * step), win_max)
    win = cfg.get("window", {})
    ww = float(win["width_mm"]) if win.get("width_mm") else suggest
    fits = win_min <= win_max + 1e-9
    checks.append({"rule": "整组放得下（窗宽可行区间非空）", "status": status(fits),
                   "detail": f"窗宽需在 {win_min:.2f}–{win_max:.2f} mm" + ("" if fits else "；放不下：改窄最宽件、减支数、叠放或加大盒面")})
    side_paper = (W - ww) / 2
    clearance = (ww - span) / 2
    checks.append({"rule": f"两侧留纸 ≥{rules['side_paper_min_mm']}mm", "status": status(side_paper >= rules["side_paper_min_mm"] - 1e-9),
                   "detail": f"{side_paper:.2f} mm"})
    checks.append({"rule": f"组外包络到窗边 ≥{rules['item_clearance_min_mm']}mm", "status": status(clearance >= rules["item_clearance_min_mm"] - 1e-9),
                   "detail": f"{clearance:.2f} mm（按最宽处计，实际照片外框会更宽，出图后要复量）"})

    win_left = (W - ww) / 2
    win_right = win_left + ww
    if win.get("top_profile"):
        prof = [[float(a), float(b)] for a, b in win["top_profile"]]
    else:
        prof = [[0, float(win.get("top_mm", 20))], [W, float(win.get("top_mm", 20))]]
    win_bottom = float(win.get("bottom_mm", H * 2 / 3))

    # 3. 横向位置（整组居中）
    x = W / 2 - span / 2 + widths[0] / 2
    centers = [x]
    for p in pitches:
        x += p
        centers.append(x)

    # 4. 竖向
    lo, hi = rules["head_below_window_top_mm"]
    m = rules["handle_end_margin_mm"]
    out_items = []
    for it, cx, wd in zip(items, centers, widths):
        L = float(it["length_mm"])
        wt = interp(prof, cx)
        place = it.get("place", {"head_gap_mm": (lo + hi) / 2})
        if place.get("align") == "bottom":
            bottom = inner_bottom - float(place.get("offset_mm", 0))
            top = bottom - L
        elif "top_mm" in place:
            top = float(place["top_mm"])
            bottom = top + L
        else:
            top = wt + float(place.get("head_gap_mm", (lo + hi) / 2))
            bottom = top + L
        head_gap = top - wt
        riser = inner_bottom - bottom
        rec = {"name": it["name"], "length_mm": L, "max_width_mm": wd, "center_x_mm": round(cx, 2),
               "left_mm": round(cx - wd / 2, 2), "right_mm": round(cx + wd / 2, 2),
               "window_top_at_column_mm": round(wt, 2), "top_mm": round(top, 2), "bottom_mm": round(bottom, 2),
               "head_below_window_top_mm": round(head_gap, 2), "riser_mm": round(riser, 2)}
        if bottom >= win_bottom:
            rec["handle_end"] = f"压纸 {bottom - win_bottom:.2f} mm"
            end_ok = bottom - win_bottom >= m - 1e-9
        else:
            rec["handle_end"] = f"窗内，离窗底 {win_bottom - bottom:.2f} mm"
            end_ok = win_bottom - bottom >= m - 1e-9
        rec["checks"] = [
            {"rule": "头部在窗内（头顶不高于窗沿）", "status": status(head_gap >= 0), "detail": f"{head_gap:.2f} mm"},
            {"rule": f"头顶低于窗沿 {lo}–{hi}mm（建议）", "status": status(lo <= head_gap <= hi, warn=head_gap >= 0),
             "detail": f"{head_gap:.2f} mm"},
            {"rule": f"柄尾窗内或压纸 ≥{m}mm", "status": status(end_ok), "detail": rec["handle_end"]},
            {"rule": "不穿出内底（垫高 ≥0）", "status": status(riser >= -1e-9), "detail": f"垫高 {riser:.2f} mm"},
            {"rule": "不超出盒面上沿", "status": status(top >= 0), "detail": f"顶 {top:.2f} mm"},
        ]
        out_items.append(rec)

    film_overlap = rules["film_overlap_mm"]
    top_min = min(p[1] for p in prof)
    film = {"width_mm": round(ww + 2 * film_overlap, 2),
            "height_mm": round(win_bottom - top_min + 2 * film_overlap, 2),
            "left_edge_to_fold_mm": round(win_left - film_overlap, 2),
            "top_edge_to_fold_mm": round(top_min - film_overlap, 2)}
    f_ok = min(film["left_edge_to_fold_mm"], film["top_edge_to_fold_mm"]) >= rules["film_to_fold_min_mm"] - 1e-9
    checks.append({"rule": f"窗膜每边大 {film_overlap}mm 后离折线 ≥{rules['film_to_fold_min_mm']}mm", "status": status(f_ok),
                   "detail": f"左右 {film['left_edge_to_fold_mm']} / 上 {film['top_edge_to_fold_mm']} mm"})
    if "decoration_top_mm" in cfg:
        d = float(cfg["decoration_top_mm"])
        checks.append({"rule": f"装饰离折线 ≥{rules['decoration_from_fold_min_mm']}mm", "status": status(d >= rules["decoration_from_fold_min_mm"]),
                       "detail": f"{d} mm"})
    if "inner_corner_radii_mm" in win:
        rmin = min(float(r) for r in win["inner_corner_radii_mm"])
        checks.append({"rule": f"窗内角 ≥R{rules['inner_corner_radius_min_mm']}", "status": status(rmin >= rules["inner_corner_radius_min_mm"]),
                       "detail": f"最小 R{rmin}"})

    all_status = [c["status"] for c in checks] + [c["status"] for r in out_items for c in r["checks"]]
    return {
        "box_mm": [W, H], "inner_bottom_mm": inner_bottom, "gap_mm": gap,
        "pitches_mm": pitches, "pitch_notes": notes, "group_span_mm": round(span, 2),
        "window": {"width_mm": ww, "suggested_width_mm": suggest, "feasible_range_mm": [round(win_min, 2), round(win_max, 2)],
                   "left_mm": round(win_left, 2), "right_mm": round(win_right, 2), "bottom_mm": win_bottom,
                   "paper_below_mm": round(H - win_bottom, 2), "side_paper_mm": round(side_paper, 2),
                   "group_clearance_each_side_mm": round(clearance, 2), "top_profile": prof},
        "film": film, "items": out_items, "checks": checks,
        "summary": {"fail": all_status.count("fail"), "warn": all_status.count("warn"), "ok": all_status.count("ok")},
        "rules_used": rules,
        "verdict": "计算与规则数据，不是刀模或合格判定；出图后按真实照片外框复量，白样确认",
    }


def to_markdown(r, title="开窗盒排布计算"):
    w = r["window"]
    L = [f"# {title}", "", f"> {r['verdict']}。AI 计算，待人工确认。", "",
         f"- 盒面 {r['box_mm'][0]}×{r['box_mm'][1]} mm，内底 {r['inner_bottom_mm']} mm，最宽处净距 {r['gap_mm']} mm",
         f"- 中心距 {' / '.join(f'{p:g}' for p in r['pitches_mm'])} mm；组宽 {r['group_span_mm']} mm"]
    for n in r["pitch_notes"]:
        L.append(f"  - {n['pair']}：计算 {n['calculated_mm']}，锁定 {n['locked_mm']}")
    L += [f"- 窗宽 {w['width_mm']} mm（建议 {w['suggested_width_mm']}，可行 {w['feasible_range_mm'][0]}–{w['feasible_range_mm'][1]}），两侧留纸 {w['side_paper_mm']} mm，组两侧净距 {w['group_clearance_each_side_mm']} mm",
          f"- 窗底 {w['bottom_mm']} mm，窗下留纸 {w['paper_below_mm']} mm；窗膜 {r['film']['width_mm']}×{r['film']['height_mm']} mm", "",
          "| 餐具 | 长 | 最宽 | 中心x | 顶 | 尾 | 头低于窗沿 | 垫高 | 柄尾 |", "|---|---|---|---|---|---|---|---|---|"]
    for i in r["items"]:
        L.append(f"| {i['name']} | {i['length_mm']:g} | {i['max_width_mm']:g} | {i['center_x_mm']} | {i['top_mm']} | {i['bottom_mm']} | {i['head_below_window_top_mm']} | {i['riser_mm']} | {i['handle_end']} |")
    L += ["", "## 规则检查", ""]
    for c in r["checks"]:
        L.append(f"- [{c['status']}] {c['rule']}：{c['detail']}")
    for i in r["items"]:
        for c in i["checks"]:
            if c["status"] != "ok":
                L.append(f"- [{c['status']}] {i['name']} {c['rule']}：{c['detail']}")
    s = r["summary"]
    L += ["", f"合计：fail {s['fail']} / warn {s['warn']} / ok {s['ok']}"]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="开窗盒餐具排布计算")
    ap.add_argument("config", help="输入 JSON")
    ap.add_argument("--json", help="结果 JSON 路径；不填打印")
    ap.add_argument("--md", help="Markdown 报告路径")
    a = ap.parse_args(argv)
    try:
        cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
        r = compute(cfg)
    except Exception as e:  # noqa: BLE001
        print(f"错误：{e}", file=sys.stderr)
        return 2
    t = json.dumps(r, ensure_ascii=False, indent=2)
    if a.json:
        Path(a.json).write_text(t, encoding="utf-8")
    else:
        print(t)
    if a.md:
        Path(a.md).write_text(to_markdown(r, cfg.get("title", "开窗盒排布计算")), encoding="utf-8")
    return 1 if r["summary"]["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
