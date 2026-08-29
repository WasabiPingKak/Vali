#!/usr/bin/env python3
"""馬來西亞聚落:分配腳本

從 locations/my-{州代碼}.json 點池抽出各州配額,產出:
  - 馬來西亞聚落.json   合併匯入檔(檔名與 name 欄位取自資料夾名)
  - point-counts.md     點池與配額統計

不產生 distribution.json:行政區分佈由 CasualGuessr 匯入時自動計算。

點池來源:`Buildings200 gte 4 and Roads0 gte 2`(聚落圖共通過濾條件)、
間距 150m,逐州跑滿。

分配規則:
  - 每州/聯邦直轄區上限 900 點,點池不足者全收
  - 邊境過濾(單一國家地圖限定):剔除鄰國(泰國、印尼、汶萊、新加坡)
    境內或距其邊界約 250m 內的點,連馬來西亞側貼線點一起剔,
    避免外部工具的粗邊界資料誤判歸屬
  - 前端相容過濾:剔除 country-coder(CasualGuessr 前端判國套件)MY 多邊形
    外的點。注意 country-coder 的 MY feature 本身沒有多邊形,實際幾何在
    「半島馬來西亞」與「東馬」兩個子 feature,要取聯集
  - 船拍過濾:剔除不在馬來西亞陸地內且離岸超過約 400m 的點;400m 內的
    「離岸」點多是邊界資料精度問題(沿海道路、跨海橋、河中島),保留
  - 抽選走網格輪抽(約 11km 網格,跨格輪流取點),避免點位集中在都會區;
    格內新景(2020+)優先,不足配額才用舊景補位
  - 抽選用固定 seed,同輸入重跑結果相同
  - 匯入檔每點在 tags 追加州代碼(MY-XX),方便在地圖編輯器中篩選

邊界資料(geoBoundaries gbOpen,GADM 站台連不上時的替代來源):
scripts/geoBoundaries-MYS-ADM0.geojson 與 THA / IDN / BRN / SGP 同名檔、
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
CAP = 900
SEED = 42
NEW_YEAR = 2020  # 新景門檻
NEIGHBOR_FUZZ_DEG = 0.0025  # 距鄰國邊界約 250m 內視為模糊地帶,剔除
OFFSHORE_DEG = 0.004  # 離馬來西亞陸地約 400m 外視為船拍點,剔除
GRID_DEG = 0.1  # 抽選網格邊長,約 11km

STATES = {
    "01": "柔佛", "02": "吉打", "03": "吉蘭丹", "04": "馬六甲",
    "05": "森美蘭", "06": "彭亨", "07": "檳城", "08": "霹靂",
    "09": "玻璃市", "10": "雪蘭莪", "11": "登嘉樓", "12": "沙巴",
    "13": "砂拉越", "14": "吉隆坡", "15": "納閩", "16": "布城",
}

NEIGHBOR_FILES = [
    "geoBoundaries-THA-ADM0.geojson",
    "geoBoundaries-IDN-ADM0.geojson",
    "geoBoundaries-BRN-ADM0.geojson",
    "geoBoundaries-SGP-ADM0.geojson",
]


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
    """剔除鄰國模糊地帶、前端判非馬來西亞的點與離岸船拍點。

    向量化 + prepared geometry:dwithin 含「在多邊形內」的情況
    (境內距離為 0),所以一個判斷式同時涵蓋境內與貼近邊界。
    """
    print("載入邊界資料...", flush=True)
    malaysia = load_boundary("geoBoundaries-MYS-ADM0.geojson")
    neighbors = shapely.union_all([load_boundary(f) for f in NEIGHBOR_FILES])
    cc_borders = json.loads(
        (SCRIPTS_DIR / "country-coder-borders.json").read_text(encoding="utf-8")
    )
    # country-coder 的 MY feature 沒有 geometry(虛擬分組),實際多邊形在
    # 「Peninsular Malaysia」「East Malaysia」兩個子 feature(country == "MY")
    cc_my = shapely.union_all([
        shape(f["geometry"]) for f in cc_borders["features"]
        if f.get("geometry")
        and (f["properties"].get("iso1A2") == "MY"
             or f["properties"].get("country") == "MY")
    ])
    shapely.prepare(malaysia)
    shapely.prepare(neighbors)
    shapely.prepare(cc_my)

    filtered = {}
    for st in sorted(pools):
        pool = pools[st]
        pts = shapely.points(
            [loc["lng"] for loc in pool], [loc["lat"] for loc in pool]
        )
        near_fo = shapely.dwithin(neighbors, pts, NEIGHBOR_FUZZ_DEG)
        cc_foreign = ~shapely.contains(cc_my, pts) & ~near_fo
        boat = ~shapely.dwithin(malaysia, pts, OFFSHORE_DEG) & ~near_fo & ~cc_foreign
        filtered[st] = [
            loc for loc, drop in zip(pool, near_fo | cc_foreign | boat) if not drop
        ]
        if near_fo.any() or cc_foreign.any() or boat.any():
            print(
                f"  MY-{st}: 剔除鄰國模糊帶 {int(near_fo.sum())}、"
                f"前端判非MY {int(cc_foreign.sum())}、"
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


def write_point_counts(pools, quotas, today):
    total_pool = sum(len(p) for p in pools.values())
    total_quota = sum(quotas.values())
    lines = [
        f"# {MAP_NAME}:各州點位統計",
        "",
        f"更新日期:{today}",
        "策略:`EvenlyByDistanceWithinCountry` + `fixedMinDistance: 150`,"
        "全州不框 geojson,輸出鎖定官方 panoId",
        "Filter:`Buildings200 gte 4 and Roads0 gte 2`"
        "(200m 內至少 4 棟建築且至少 2 條道路),聚落圖共通條件",
        "邊境/船拍過濾:剔除距鄰國(泰、印尼、汶萊、星)邊界約 250m 內的"
        "模糊帶點、country-coder(前端判國套件)MY 多邊形外的點,"
        "與離馬來西亞陸地約 400m 外的船拍/水上點(本地 point-in-polygon)",
        f"點池總量:**16 州/聯邦直轄區 / {fmt(total_pool)} 點**;"
        f"地圖配額:**{fmt(total_quota)} 點**"
        f"(每州上限 {fmt(CAP)},點池不足者全收)",
        "抽選:約 11km 網格輪抽(跨格輪流取點,避免集中都會區),格內新景 2020+ 優先",
        "行政區分佈不輸出 distribution.json,由 CasualGuessr 匯入時自動計算",
        "依點池大小排序。",
        "",
        "| 排名 | 代碼 | 州/聯邦直轄區 | 點池 | 配額 | 佔全圖 |",
        "|---|---|---|---|---|---|",
    ]
    order = sorted(pools, key=lambda p: (-len(pools[p]), p))
    for rank, st in enumerate(order, 1):
        q = quotas[st]
        lines.append(
            f"| {rank} | MY-{st} | {STATES[st]} | {fmt(len(pools[st]))} "
            f"| {fmt(q)} | {q / total_quota * 100:.2f}% |"
        )
    (MAP_DIR / "point-counts.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    today = date.today().isoformat()
    pools = {}
    for st in STATES:
        pools[st] = json.loads(
            (MAP_DIR / "locations" / f"my-{st}.json").read_text(encoding="utf-8")
        )
    pools = border_filter(pools)

    quotas = {st: min(len(pool), CAP) for st, pool in pools.items()}
    merged = []
    for st in sorted(pools):
        chosen = select_locations(st, pools[st], quotas[st])
        for loc in chosen:
            extra = dict(loc.get("extra") or {})
            extra["tags"] = list(extra.get("tags") or []) + [f"MY-{st}"]
            merged.append({**loc, "extra": extra})

    (MAP_DIR / f"{MAP_NAME}.json").write_text(
        json.dumps({"name": MAP_NAME, "customCoordinates": merged},
                   ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    write_point_counts(pools, quotas, today)

    print(f"合計 {fmt(len(merged))} 點")
    for st in sorted(quotas, key=lambda p: (-quotas[p], p)):
        print(f"  MY-{st} {STATES[st]}: {fmt(quotas[st])}")


if __name__ == "__main__":
    main()
