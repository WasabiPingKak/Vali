#!/usr/bin/env python3
"""加拿大北部地區:分配腳本

點池沿用「A Provincially Balanced Canada 平衡省份的加拿大」產出的各省/地區結果
(同一套 Vali config 與 filter),重新分配成北部為主的地圖。

從 locations/{地區代碼}.json 點池抽出各區配額,產出:
  - {地圖名}.json      合併匯入檔(檔名與 name 欄位取自資料夾名)
  - point-counts.md    點池與配額統計
  - distribution.json  各區落點數量統計(ISO 3166-2 代碼)

分配規則:
  - 北部三區為主體:YT 500 點,NT 與 NU 點池不足 500,全收
  - 南部十省各 38 點,讓地圖不會百分之百落在北部,北部佔比維持在 75% 左右
  - 邊境過濾(單一國家地圖限定):剔除美國境內或距美國邊界約 250m 內的點,
    連加拿大側貼線點一起剔(YT 與阿拉斯加相鄰),避免外部工具的粗邊界資料
    誤判地區歸屬
  - 前端相容過濾:剔除 country-coder(CasualGuessr 前端判國套件)CA 多邊形
    外的點,保證上傳後每點都判得進地區
  - 船拍過濾:剔除不在加拿大陸地內且離岸超過約 400m 的點;400m 內的「離岸」
    點多是 GADM 精度問題(沿海道路、橋樑、河中島),保留
  - 抽選走網格輪抽(約 11km 網格,跨格輪流取點),避免點位集中在城鎮或都會區;
    格內新景(2020+)優先,不足配額才用舊景補位
  - 抽選用固定 seed,同輸入重跑結果相同
  - 匯入檔每點在 tags 追加地區代碼,方便在地圖編輯器中篩選

邊界資料:scripts/gadm41_CAN_0.json、scripts/gadm41_USA_0.json(GADM 4.1)、
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

MAP_DIR = Path(__file__).parent
MAP_NAME = MAP_DIR.name
SCRIPTS_DIR = MAP_DIR.parent.parent / "scripts"
SEED = 42
NEW_YEAR = 2020  # 新景門檻
US_FUZZ_DEG = 0.0025  # 距美國邊界約 250m 內視為模糊地帶,剔除
OFFSHORE_DEG = 0.004  # 離加拿大陸地約 400m 外視為船拍點,剔除
GRID_DEG = 0.1  # 抽選網格邊長,約 11km
NORTH_CAP = 500  # 北部三區上限,NT / NU 點池不足即全收
SOUTH_CAP = 38  # 南部十省每省配額,調這個數字即可改變北部佔比(38 -> 北部約 75%)

# 代碼 -> (中文名, 上限)
REGIONS = {
    "YT": ("育空", NORTH_CAP),
    "NT": ("西北地方", NORTH_CAP),
    "NU": ("努納武特", NORTH_CAP),
    "AB": ("亞伯達", SOUTH_CAP),
    "BC": ("英屬哥倫比亞", SOUTH_CAP),
    "MB": ("曼尼托巴", SOUTH_CAP),
    "NB": ("紐布藍茲維", SOUTH_CAP),
    "NL": ("紐芬蘭與拉布拉多", SOUTH_CAP),
    "NS": ("新斯科細亞", SOUTH_CAP),
    "ON": ("安大略", SOUTH_CAP),
    "PE": ("愛德華王子島", SOUTH_CAP),
    "QC": ("魁北克", SOUTH_CAP),
    "SK": ("薩斯喀徹溫", SOUTH_CAP),
}
NORTH = ("YT", "NT", "NU")


def sorted_codes(quotas: dict[str, int]) -> list[str]:
    """北部三區排前面,各組內依實際配額由多到少。"""
    return sorted(quotas, key=lambda c: (c not in NORTH, -quotas[c], c))


def load_gadm(name: str):
    path = SCRIPTS_DIR / name
    if not path.exists():
        sys.exit(
            f"找不到邊界資料 {path},請執行:\n"
            f"curl -sL https://geodata.ucdavis.edu/gadm/gadm4.1/json/{name} -o {path}"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return shape(data["features"][0]["geometry"])


def border_filter(pools: dict[str, list]) -> dict[str, list]:
    """剔除美國模糊地帶與船拍點,回傳過濾後的點池並列印剔除明細。

    向量化 + prepared geometry:dwithin 含「在多邊形內」的情況
    (境內距離為 0),所以一個判斷式同時涵蓋境內與貼近邊界。
    """
    print("載入邊界資料...", flush=True)
    canada = load_gadm("gadm41_CAN_0.json")
    usa = load_gadm("gadm41_USA_0.json")
    cc_borders = json.loads(
        (SCRIPTS_DIR / "country-coder-borders.json").read_text(encoding="utf-8")
    )
    cc_ca = shape(
        next(f["geometry"] for f in cc_borders["features"]
             if f["properties"].get("iso1A2") == "CA")
    )
    shapely.prepare(canada)
    shapely.prepare(usa)
    shapely.prepare(cc_ca)

    filtered = {}
    for terr in sorted(pools):
        pool = pools[terr]
        pts = shapely.points(
            [loc["lng"] for loc in pool], [loc["lat"] for loc in pool]
        )
        near_us = shapely.dwithin(usa, pts, US_FUZZ_DEG)
        cc_foreign = ~shapely.contains(cc_ca, pts) & ~near_us
        boat = ~shapely.dwithin(canada, pts, OFFSHORE_DEG) & ~near_us & ~cc_foreign
        filtered[terr] = [
            loc for loc, drop in zip(pool, near_us | cc_foreign | boat) if not drop
        ]
        if near_us.any() or cc_foreign.any() or boat.any():
            print(
                f"  {terr}: 剔除美國模糊帶 {int(near_us.sum())}、"
                f"前端判非CA {int(cc_foreign.sum())}、"
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


def select_locations(terr: str, pool: list, quota: int) -> list:
    """網格輪抽:點池切網格,跨網格一輪一輪各取一點,直到配額滿。

    均勻隨機抽會讓城鎮點數等比於街景密度,輪抽把每格點數拉平,
    白馬市、黃刀鎮這類北部主要城鎮不再獨佔配額。
    格內排序為新景(2020+)優先、同組隨機,所以每格先貢獻最新的街景。
    結果維持點池原順序。
    """
    rng = random.Random(f"{SEED}:{terr}")
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
    north_quota = sum(quotas[c] for c in NORTH)
    lines = [
        f"# {MAP_NAME}:各省/地區點位統計",
        "",
        f"更新日期:{today}",
        "範圍:以育空、西北地方、努納武特三個北部地區為主體,"
        "南部十省各配少量點位;點池沿用"
        "「A Provincially Balanced Canada 平衡省份的加拿大」的產出",
        "策略:`EvenlyByDistanceWithinCountry` + `fixedMinDistance: 100`,"
        "全區不框 geojson,輸出鎖定官方 panoId",
        "Filter:`Roads0 gt 2 or ArrowCount gte 3 or ClosestRiver lt 100 "
        "or ClosestRailway lt 100` + 預設 filter(排隧道、壞圖),不看建築密度",
        "邊境/船拍過濾:剔除距美國邊界約 250m 內的模糊帶點、"
        "country-coder(前端判國套件)CA 多邊形外的點,"
        "與離加拿大陸地約 400m 外的船拍/水上點(本地 point-in-polygon)",
        f"點池總量:**13 省/地區 / {fmt(total_pool)} 點**;"
        f"地圖配額:**{fmt(total_quota)} 點**"
        f"(北部三區上限 {fmt(NORTH_CAP)}、南部十省各 {fmt(SOUTH_CAP)},"
        "點池不足者全收)",
        f"北部佔比:**{north_quota / total_quota * 100:.1f}%**"
        f"({fmt(north_quota)} 點)",
        "抽選:約 11km 網格輪抽(跨格輪流取點,避免集中城鎮或都會區),"
        "格內新景 2020+ 優先",
        "",
        "| 代碼 | 省/地區 | 點池 | 配額 | 新景 | 佔全圖 |",
        "|---|---|---|---|---|---|",
    ]
    for code in sorted_codes(quotas):
        q = quotas[code]
        lines.append(
            f"| {code} | {REGIONS[code][0]} | {fmt(len(pools[code]))} | {fmt(q)} "
            f"| {fmt(new_counts[code])} | {q / total_quota * 100:.2f}% |"
        )
    (MAP_DIR / "point-counts.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    today = date.today().isoformat()
    pools = {}
    for code in REGIONS:
        pools[code] = json.loads(
            (MAP_DIR / "locations" / f"{code.lower()}.json").read_text(encoding="utf-8")
        )
    pools = border_filter(pools)

    quotas = {code: min(len(pool), REGIONS[code][1]) for code, pool in pools.items()}
    merged = []
    new_counts = {}
    for code in sorted(pools):
        chosen = select_locations(code, pools[code], quotas[code])
        new_counts[code] = sum(1 for loc in chosen if year(loc) >= NEW_YEAR)
        for loc in chosen:
            extra = dict(loc.get("extra") or {})
            extra["tags"] = list(extra.get("tags") or []) + [code]
            merged.append({**loc, "extra": extra})

    (MAP_DIR / f"{MAP_NAME}.json").write_text(
        json.dumps({"name": MAP_NAME, "customCoordinates": merged},
                   ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    region_lines = ",\n".join(
        f'    {{ "code": "CA-{code}", "count": {quotas[code]} }}'
        for code in sorted_codes(quotas)
    )
    (MAP_DIR / "distribution.json").write_text(
        '{\n  "regions": [\n' + region_lines + "\n  ]\n}\n",
        encoding="utf-8",
    )
    write_point_counts(pools, quotas, new_counts, today)

    north_quota = sum(quotas[c] for c in NORTH)
    print(f"合計 {fmt(len(merged))} 點"
          f"(北部 {fmt(north_quota)},佔 {north_quota / len(merged) * 100:.1f}%)")
    for code in sorted_codes(quotas):
        print(f"  {code} {REGIONS[code][0]}: {fmt(quotas[code])}"
              f"(新景 {fmt(new_counts[code])})")


if __name__ == "__main__":
    main()
