#!/usr/bin/env python3
"""A Regionally Balanced New Zealand 平衡大區的紐西蘭:分配腳本

從 locations/{大區代碼小寫}.json 點池抽出各大區配額,產出:
  - {地圖名}.json      合併匯入檔(檔名與 name 欄位取自資料夾名)
  - point-counts.md    點池與配額統計

不產生 distribution.json:行政區分佈由 CasualGuessr 匯入時自動計算。

分配規則:
  - 每個大區上限 CAP 點,點池不足者全收;個別大區可用 CAP_OVERRIDES 調整
    (例如尼爾森只有一座城市,面積 445 km²,可視情況給較低配額)
  - 查塔姆群島領地(NZ-CIT)沒有街景資料,不納入地圖
  - 紐西蘭沒有陸地鄰國,不做鄰國模糊帶過濾
  - 前端相容過濾:剔除 country-coder(CasualGuessr 前端判國套件)NZ 多邊形
    外的點,保證上傳後每點都判為紐西蘭。庫克群島、紐埃、托克勞在
    country-coder 有各自代碼(CK、NU、TK),不算 NZ 多邊形
  - 船拍過濾:剔除不在紐西蘭陸地內且離岸超過約 400m 的點;400m 內的
    「離岸」點多是邊界資料精度問題(沿海道路、跨海橋、河中島),保留
  - 抽選走網格輪抽(約 11km 網格,跨格輪流取點),避免點位集中在都會區;
    格內新景(2020+)優先,不足配額才用舊景補位
  - 抽選用固定 seed,同輸入重跑結果相同
  - 匯入檔每點在 tags 追加大區代碼(NZ-XXX),方便在地圖編輯器中篩選

邊界資料:
scripts/geoBoundaries-NZL-ADM0.geojson(geoBoundaries gbOpen,NZ Stats 版,
原檔 106MB 太大,已用 shapely 以 0.0003 度(約 30m)容差簡化到 3.4MB,
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
CAP = 1_500
CAP_OVERRIDES: dict[str, int] = {}
SEED = 42
NEW_YEAR = 2020  # 新景門檻
OFFSHORE_DEG = 0.004  # 離紐西蘭陸地約 400m 外視為船拍點,剔除
GRID_DEG = 0.1  # 抽選網格邊長,約 11km

REGIONS = {
    "AUK": "奧克蘭",
    "BOP": "豐盛灣",
    "CAN": "坎特伯雷",
    "GIS": "吉斯伯恩",
    "HKB": "霍克灣",
    "MBH": "馬爾堡",
    "MWT": "馬納瓦圖-旺加努伊",
    "NSN": "尼爾森",
    "NTL": "北地",
    "OTA": "奧塔哥",
    "STL": "南地",
    "TAS": "塔斯曼",
    "TKI": "塔拉納基",
    "WGN": "威靈頓",
    "WKO": "懷卡托",
    "WTC": "西岸",
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
    """剔除前端判非紐西蘭的點與離岸船拍點。

    向量化 + prepared geometry:dwithin 含「在多邊形內」的情況
    (境內距離為 0),所以一個判斷式同時涵蓋境內與貼近海岸。
    """
    print("載入邊界資料...", flush=True)
    nz = load_boundary("geoBoundaries-NZL-ADM0.geojson")
    cc_borders = json.loads(
        (SCRIPTS_DIR / "country-coder-borders.json").read_text(encoding="utf-8")
    )
    # country-coder 的 NZ feature 沒有 geometry(虛擬分組),實際多邊形在
    # 「North Island」「South Island」「Stewart Island」「Chatham Islands」等
    # 子 feature(country == "NZ" 且無 iso1A2)。有自己 iso1A2 的
    # 庫克群島、紐埃、托克勞(CK、NU、TK)前端會判成別的代碼,不算進來
    cc_nz = shapely.union_all([
        shape(f["geometry"]) for f in cc_borders["features"]
        if f.get("geometry")
        and f["properties"].get("country") == "NZ"
        and not f["properties"].get("iso1A2")
    ])
    shapely.prepare(nz)
    shapely.prepare(cc_nz)

    filtered = {}
    for rg in sorted(pools):
        pool = pools[rg]
        pts = shapely.points(
            [loc["lng"] for loc in pool], [loc["lat"] for loc in pool]
        )
        cc_foreign = ~shapely.contains(cc_nz, pts)
        boat = ~shapely.dwithin(nz, pts, OFFSHORE_DEG) & ~cc_foreign
        filtered[rg] = [
            loc for loc, drop in zip(pool, cc_foreign | boat) if not drop
        ]
        if cc_foreign.any() or boat.any():
            print(
                f"  NZ-{rg}: 剔除前端判非NZ {int(cc_foreign.sum())}、"
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


def select_locations(rg: str, pool: list, quota: int) -> list:
    """網格輪抽:點池切網格,跨網格一輪一輪各取一點,直到配額滿。

    均勻隨機抽會讓城市點數等比於街景密度,輪抽把每格點數拉平,
    都會區不再獨佔配額。格內排序為新景(2020+)優先、同組隨機,
    所以每格先貢獻最新的街景。結果維持點池原順序。
    """
    rng = random.Random(f"{SEED}:{rg}")
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
            f"{REGIONS[rg]} {fmt(c)}" for rg, c in CAP_OVERRIDES.items()
        )
        if CAP_OVERRIDES else ""
    )
    lines = [
        f"# {MAP_NAME}:各大區點位統計",
        "",
        f"更新日期:{today}",
        "策略:`EvenlyByDistanceWithinCountry` + `fixedMinDistance: 100`,"
        "全區不框 geojson,輸出鎖定官方 panoId",
        "Filter:`Roads0 gt 2 or ArrowCount gte 3 or ClosestRiver lt 100 "
        "or ClosestRailway lt 100` + 預設 filter(排隧道、壞圖),不看建築密度",
        "邊境/船拍過濾:紐西蘭沒有陸地鄰國,只剔除 country-coder(前端判國套件)"
        "NZ 多邊形外的點,與離紐西蘭陸地約 400m 外的船拍/水上點(本地 point-in-polygon)",
        "查塔姆群島領地(NZ-CIT)沒有街景資料,不納入",
        f"點池總量:**{len(pools)} 大區 / {fmt(total_pool)} 點**;"
        f"地圖配額:**{fmt(total_quota)} 點**"
        f"(每區上限 {fmt(CAP)}{override_note},點池不足者全收)",
        "抽選:約 11km 網格輪抽(跨格輪流取點,避免集中都會區),格內新景 2020+ 優先",
        "行政區分佈不輸出 distribution.json,由 CasualGuessr 匯入時自動計算",
        "依點池大小排序。",
        "",
        "| 排名 | 代碼 | 大區 | 點池 | 配額 | 新景 | 佔全圖 |",
        "|---|---|---|---|---|---|---|",
    ]
    order = sorted(pools, key=lambda p: (-len(pools[p]), p))
    for rank, rg in enumerate(order, 1):
        q = quotas[rg]
        lines.append(
            f"| {rank} | NZ-{rg} | {REGIONS[rg]} | {fmt(len(pools[rg]))} "
            f"| {fmt(q)} | {fmt(new_counts[rg])} | {q / total_quota * 100:.2f}% |"
        )
    (MAP_DIR / "point-counts.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    today = date.today().isoformat()
    pools = {}
    for rg in REGIONS:
        pools[rg] = json.loads(
            (MAP_DIR / "locations" / f"{rg.lower()}.json").read_text(encoding="utf-8")
        )
    pools = border_filter(pools)

    quotas = {
        rg: min(len(pool), CAP_OVERRIDES.get(rg, CAP)) for rg, pool in pools.items()
    }
    merged, new_counts = [], {}
    for rg in sorted(pools):
        chosen = select_locations(rg, pools[rg], quotas[rg])
        new_counts[rg] = sum(1 for loc in chosen if year(loc) >= NEW_YEAR)
        for loc in chosen:
            extra = dict(loc.get("extra") or {})
            extra["tags"] = list(extra.get("tags") or []) + [f"NZ-{rg}"]
            merged.append({**loc, "extra": extra})

    (MAP_DIR / f"{MAP_NAME}.json").write_text(
        json.dumps({"name": MAP_NAME, "customCoordinates": merged},
                   ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    write_point_counts(pools, quotas, new_counts, today)

    print(f"合計 {fmt(len(merged))} 點")
    for rg in sorted(quotas, key=lambda p: (-quotas[p], p)):
        print(f"  NZ-{rg} {REGIONS[rg]}: {fmt(quotas[rg])} (點池 {fmt(len(pools[rg]))})")


if __name__ == "__main__":
    main()
