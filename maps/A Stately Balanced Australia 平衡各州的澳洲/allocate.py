#!/usr/bin/env python3
"""A Stately Balanced Australia 平衡各州的澳洲:分配腳本

從 locations/{州代碼小寫}.json 點池抽出各州配額,產出:
  - {地圖名}.json      合併匯入檔(檔名與 name 欄位取自資料夾名)
  - point-counts.md    點池與配額統計

不產生 distribution.json:行政區分佈由 CasualGuessr 匯入時自動計算。

分配規則:
  - 每州/領地上限 CAP 點,點池不足者全收;個別州可用 CAP_OVERRIDES 調整
    (例如首都領地只有坎培拉一座城市,可視情況給較低配額)
  - Jervis Bay Territory 點池只有 1 點,不納入地圖
  - 澳洲沒有陸地鄰國,不做鄰國模糊帶過濾
  - 前端相容過濾:剔除 country-coder(CasualGuessr 前端判國套件)AU 多邊形
    外的點,保證上傳後每點都判為澳洲。聖誕島、科科斯群島、諾福克島等
    外部領地在 country-coder 有各自代碼,不算 AU 多邊形
  - 船拍過濾:剔除不在澳洲陸地內且離岸超過約 400m 的點;400m 內的
    「離岸」點多是邊界資料精度問題(沿海道路、跨海橋、河中島),保留
  - 抽選走網格輪抽(約 11km 網格,跨格輪流取點),避免點位集中在都會區;
    格內新景(2020+)優先,不足配額才用舊景補位
  - 抽選用固定 seed,同輸入重跑結果相同
  - 匯入檔每點在 tags 追加州代碼(AU-XXX),方便在地圖編輯器中篩選

邊界資料:
scripts/geoBoundaries-AUS-ADM0.geojson(geoBoundaries gbOpen,ABS 2021 版,
原檔 66MB 太大,已用 shapely 以 0.0003 度(約 30m)容差簡化到 9.5MB,
島嶼數與面積不變,對 400m 的離岸判斷沒有影響)、
scripts/country-coder-borders.json(@rapideditor/country-coder 的 borders.json)
需要 shapely:pip install shapely

用法:
  python allocate.py
"""

import json
import math
import random
import sys
from datetime import date
from pathlib import Path

try:
    import shapely
    from shapely.geometry import shape
except ImportError:
    print("需要 shapely: pip install shapely", file=sys.stderr)
    sys.exit(1)

# Windows 主控台預設 cp950 可能印不出部分字元,避免統計印到一半崩潰
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAP_DIR = Path(__file__).parent
MAP_NAME = MAP_DIR.name
SCRIPTS_DIR = MAP_DIR.parent.parent / "scripts"
CAP = 3_000
CAP_OVERRIDES: dict[str, int] = {"ACT": 1_500}  # 首都領地只有坎培拉一座城市,減半
SEED = 42
NEW_YEAR = 2020  # 新景門檻
OFFSHORE_DEG = 0.004  # 離澳洲陸地約 400m 外視為船拍點,剔除
GRID_DEG = 0.1  # 抽選網格邊長,約 11km

STATES = {
    "ACT": "澳洲首都領地",
    "NSW": "新南威爾斯",
    "NT": "北領地",
    "QLD": "昆士蘭",
    "SA": "南澳",
    "TAS": "塔斯馬尼亞",
    "VIC": "維多利亞",
    "WA": "西澳",
}


def load_boundary(name: str):
    path = SCRIPTS_DIR / name
    if not path.exists():
        sys.exit(
            f"找不到邊界資料 {path},下載連結可從 geoBoundaries API 取得:\n"
            f"https://www.geoboundaries.org/api/current/gbOpen/<ISO3>/ADM0/"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return shape(data["features"][0]["geometry"])


def border_filter(pools: dict[str, list]) -> dict[str, list]:
    """剔除前端判非澳洲的點與離岸船拍點。

    向量化 + prepared geometry:dwithin 含「在多邊形內」的情況
    (境內距離為 0),所以一個判斷式同時涵蓋境內與貼近海岸。
    """
    print("載入邊界資料...", flush=True)
    australia = load_boundary("geoBoundaries-AUS-ADM0.geojson")
    cc_borders = json.loads(
        (SCRIPTS_DIR / "country-coder-borders.json").read_text(encoding="utf-8")
    )
    # country-coder 的 AU feature 沒有 geometry(虛擬分組),實際多邊形在
    # 「Mainland Australia」「Tasmania」等子 feature(country == "AU" 且無 iso1A2)。
    # 有自己 iso1A2 的外部領地(CX、CC、NF、HM)前端會判成別的代碼,不算進來
    cc_au = shapely.union_all([
        shape(f["geometry"]) for f in cc_borders["features"]
        if f.get("geometry")
        and f["properties"].get("country") == "AU"
        and not f["properties"].get("iso1A2")
    ])
    shapely.prepare(australia)
    shapely.prepare(cc_au)

    filtered = {}
    for st in sorted(pools):
        pool = pools[st]
        pts = shapely.points(
            [loc["lng"] for loc in pool], [loc["lat"] for loc in pool]
        )
        cc_foreign = ~shapely.contains(cc_au, pts)
        boat = ~shapely.dwithin(australia, pts, OFFSHORE_DEG) & ~cc_foreign
        filtered[st] = [
            loc for loc, drop in zip(pool, cc_foreign | boat) if not drop
        ]
        if cc_foreign.any() or boat.any():
            print(
                f"  AU-{st}: 剔除前端判非AU {int(cc_foreign.sum())}、"
                f"船拍/水上 {int(boat.sum())}",
                flush=True,
            )
    return filtered


def year(loc) -> int:
    tags = (loc.get("extra") or {}).get("tags") or []
    try:
        return int(tags[1])
    except (IndexError, ValueError):
        return 0


def grid_cell(loc) -> tuple[int, int]:
    """把座標歸進約 11km 見方的網格(經度隨緯度收斂,用 cos 補償)。"""
    lat = loc["lat"]
    lng_size = GRID_DEG / max(math.cos(math.radians(lat)), 0.15)
    return int(lat / GRID_DEG), int(loc["lng"] / lng_size)


def select_locations(st: str, pool: list, quota: int) -> list:
    """網格輪抽:點池切網格,跨網格一輪一輪各取一點,直到配額滿。

    均勻隨機抽會讓城市點數等比於街景密度,輪抽把每格點數拉平,
    都會區不再獨佔配額。格內排序為新景(2020+)優先、同組隨機,
    所以每格先貢獻最新的街景。結果維持點池原順序。
    """
    rng = random.Random(f"{SEED}:{st}")
    buckets: dict[tuple[int, int], list] = {}
    for i, loc in enumerate(pool):
        buckets.setdefault(grid_cell(loc), []).append((i, loc))
    for b in buckets.values():
        b.sort(key=lambda t: (year(t[1]) >= NEW_YEAR, rng.random()), reverse=True)

    keys = sorted(buckets)
    rng.shuffle(keys)  # 配額用罄時,決定哪些格子多拿一點的順序要隨機

    chosen, round_i = [], 0
    while len(chosen) < quota:
        progressed = False
        for k in keys:
            if round_i < len(buckets[k]):
                chosen.append(buckets[k][round_i])
                progressed = True
                if len(chosen) >= quota:
                    break
        if not progressed:  # 所有格子都取完仍不足配額
            break
        round_i += 1
    return [loc for _, loc in sorted(chosen, key=lambda t: t[0])]


def fmt(n: int) -> str:
    return f"{n:,}"


def write_point_counts(pools, quotas, new_counts, today):
    total_pool = sum(len(p) for p in pools.values())
    total_quota = sum(quotas.values())
    override_note = (
        ",個別調整:" + "、".join(
            f"{STATES[st]} {fmt(c)}" for st, c in CAP_OVERRIDES.items()
        )
        if CAP_OVERRIDES else ""
    )
    lines = [
        f"# {MAP_NAME}:各州點位統計",
        "",
        f"更新日期:{today}",
        "策略:`EvenlyByDistanceWithinCountry` + `fixedMinDistance: 100`,"
        "全州不框 geojson,輸出鎖定官方 panoId",
        "Filter:`Roads0 gt 2 or ArrowCount gte 3 or ClosestRiver lt 100 "
        "or ClosestRailway lt 100` + 預設 filter(排隧道、壞圖),不看建築密度",
        "邊境/船拍過濾:澳洲沒有陸地鄰國,只剔除 country-coder(前端判國套件)"
        "AU 多邊形外的點,與離澳洲陸地約 400m 外的船拍/水上點(本地 point-in-polygon)",
        "Jervis Bay Territory 點池只有 1 點,不納入",
        f"點池總量:**{len(pools)} 州/領地 / {fmt(total_pool)} 點**;"
        f"地圖配額:**{fmt(total_quota)} 點**"
        f"(每州上限 {fmt(CAP)}{override_note},點池不足者全收)",
        "抽選:約 11km 網格輪抽(跨格輪流取點,避免集中都會區),格內新景 2020+ 優先",
        "行政區分佈不輸出 distribution.json,由 CasualGuessr 匯入時自動計算",
        "依點池大小排序。",
        "",
        "| 排名 | 代碼 | 州/領地 | 點池 | 配額 | 新景 | 佔全圖 |",
        "|---|---|---|---|---|---|---|",
    ]
    order = sorted(pools, key=lambda p: (-len(pools[p]), p))
    for rank, st in enumerate(order, 1):
        q = quotas[st]
        lines.append(
            f"| {rank} | AU-{st} | {STATES[st]} | {fmt(len(pools[st]))} "
            f"| {fmt(q)} | {fmt(new_counts[st])} | {q / total_quota * 100:.2f}% |"
        )
    (MAP_DIR / "point-counts.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    today = date.today().isoformat()
    pools = {}
    for st in STATES:
        pools[st] = json.loads(
            (MAP_DIR / "locations" / f"{st.lower()}.json").read_text(encoding="utf-8")
        )
    pools = border_filter(pools)

    quotas = {
        st: min(len(pool), CAP_OVERRIDES.get(st, CAP)) for st, pool in pools.items()
    }
    merged, new_counts = [], {}
    for st in sorted(pools):
        chosen = select_locations(st, pools[st], quotas[st])
        new_counts[st] = sum(1 for loc in chosen if year(loc) >= NEW_YEAR)
        for loc in chosen:
            extra = dict(loc.get("extra") or {})
            extra["tags"] = list(extra.get("tags") or []) + [f"AU-{st}"]
            merged.append({**loc, "extra": extra})

    (MAP_DIR / f"{MAP_NAME}.json").write_text(
        json.dumps({"name": MAP_NAME, "customCoordinates": merged},
                   ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    write_point_counts(pools, quotas, new_counts, today)

    print(f"合計 {fmt(len(merged))} 點")
    for st in sorted(quotas, key=lambda p: (-quotas[p], p)):
        print(f"  AU-{st} {STATES[st]}: {fmt(quotas[st])} (點池 {fmt(len(pools[st]))})")


if __name__ == "__main__":
    main()
