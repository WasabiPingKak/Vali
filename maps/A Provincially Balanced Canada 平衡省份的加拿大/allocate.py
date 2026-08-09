#!/usr/bin/env python3
"""A Provincially Balanced Canada 平衡省份的加拿大:分配腳本

從 locations/{省代碼}.json 點池抽出各省配額,產出:
  - {地圖名}.json      合併匯入檔(檔名與 name 欄位取自資料夾名)
  - point-counts.md    點池與配額統計
  - distribution.json  各省落點數量統計(ISO 3166-2 代碼)

分配規則:
  - 每省/地區上限 2,000 點,點池不足者全收(YT、NT、NU)
  - 邊境過濾(單一國家地圖限定):剔除美國境內或距美國邊界約 250m 內的點,
    連加拿大側貼線點一起剔,避免外部工具的粗邊界資料誤判省份歸屬
  - 前端相容過濾:剔除 country-coder(CasualGuessr 前端判國套件)CA 多邊形
    外的點。它的簡化河界會把 NB 聖約翰河沿岸等加拿大側路段判給美國,
    用同一份資料預先過濾,保證上傳後每點都判得進省份
  - 船拍過濾:剔除不在加拿大陸地內且離岸超過約 400m 的點(聖羅倫斯河船拍
    coverage 會過 ClosestRiver filter);400m 內的「離岸」點多是 GADM 精度
    問題(沿海道路、橋樑、河中島),保留
  - 抽選走網格輪抽(約 11km 網格,跨格輪流取點),避免點位集中在都會區;
    格內新景(2020+)優先,不足配額才用舊景補位
  - 抽選用固定 seed,同輸入重跑結果相同
  - 匯入檔每點在 tags 追加省代碼,方便在地圖編輯器中篩選

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
CAP = 2_000
SEED = 42
NEW_YEAR = 2020  # 新景門檻
US_FUZZ_DEG = 0.0025  # 距美國邊界約 250m 內視為模糊地帶,剔除
OFFSHORE_DEG = 0.004  # 離加拿大陸地約 400m 外視為船拍點,剔除
GRID_DEG = 0.1  # 抽選網格邊長,約 11km

PROVINCES = {
    "AB": "亞伯達",
    "BC": "英屬哥倫比亞",
    "MB": "曼尼托巴",
    "NB": "紐布藍茲維",
    "NL": "紐芬蘭與拉布拉多",
    "NS": "新斯科細亞",
    "NT": "西北地方",
    "NU": "努納武特",
    "ON": "安大略",
    "PE": "愛德華王子島",
    "QC": "魁北克",
    "SK": "薩斯喀徹溫",
    "YT": "育空",
}


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
    for prov in sorted(pools):
        pool = pools[prov]
        pts = shapely.points(
            [loc["lng"] for loc in pool], [loc["lat"] for loc in pool]
        )
        near_us = shapely.dwithin(usa, pts, US_FUZZ_DEG)
        cc_foreign = ~shapely.contains(cc_ca, pts) & ~near_us
        boat = ~shapely.dwithin(canada, pts, OFFSHORE_DEG) & ~near_us & ~cc_foreign
        filtered[prov] = [
            loc for loc, drop in zip(pool, near_us | cc_foreign | boat) if not drop
        ]
        if near_us.any() or cc_foreign.any() or boat.any():
            print(
                f"  {prov}: 剔除美國模糊帶 {int(near_us.sum())}、"
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


def select_locations(prov: str, pool: list, quota: int) -> list:
    """網格輪抽:點池切網格,跨網格一輪一輪各取一點,直到配額滿。

    均勻隨機抽會讓城市點數等比於街景密度(溫尼伯曾有 372 點擠在同一個
    11km 方格),輪抽把每格點數拉平,城市不再獨佔配額。
    格內排序為新景(2020+)優先、同組隨機,所以每格先貢獻最新的街景。
    結果維持點池原順序。
    """
    rng = random.Random(f"{SEED}:{prov}")
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
    lines = [
        f"# {MAP_NAME}:各省點位統計",
        "",
        f"更新日期:{today}",
        "策略:`EvenlyByDistanceWithinCountry` + `fixedMinDistance: 100`,"
        "全省不框 geojson,輸出鎖定官方 panoId",
        "Filter:`Roads0 gt 2 or ArrowCount gte 3 or ClosestRiver lt 100 "
        "or ClosestRailway lt 100` + 預設 filter(排隧道、壞圖),不看建築密度",
        "邊境/船拍過濾:剔除距美國邊界約 250m 內的模糊帶點、"
        "country-coder(前端判國套件)CA 多邊形外的點,"
        "與離加拿大陸地約 400m 外的船拍/水上點(本地 point-in-polygon)",
        f"點池總量:**13 省/地區 / {fmt(total_pool)} 點**;"
        f"地圖配額:**{fmt(total_quota)} 點**"
        f"(每省上限 {fmt(CAP)},點池不足者全收)",
        "抽選:約 11km 網格輪抽(跨格輪流取點,避免集中都會區),格內新景 2020+ 優先",
        "",
        "| 代碼 | 省/地區 | 點池 | 配額 | 新景 | 佔全圖 |",
        "|---|---|---|---|---|---|",
    ]
    for prov in sorted(pools, key=lambda p: (-quotas[p], p)):
        q = quotas[prov]
        lines.append(
            f"| {prov} | {PROVINCES[prov]} | {fmt(len(pools[prov]))} | {fmt(q)} "
            f"| {fmt(new_counts[prov])} | {q / total_quota * 100:.2f}% |"
        )
    (MAP_DIR / "point-counts.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    today = date.today().isoformat()
    pools = {}
    for prov in PROVINCES:
        pools[prov] = json.loads(
            (MAP_DIR / "locations" / f"{prov.lower()}.json").read_text(encoding="utf-8")
        )
    pools = border_filter(pools)

    quotas = {prov: min(len(pool), CAP) for prov, pool in pools.items()}
    merged = []
    new_counts = {}
    for prov in sorted(pools):
        chosen = select_locations(prov, pools[prov], quotas[prov])
        new_counts[prov] = sum(1 for loc in chosen if year(loc) >= NEW_YEAR)
        for loc in chosen:
            extra = dict(loc.get("extra") or {})
            extra["tags"] = list(extra.get("tags") or []) + [prov]
            merged.append({**loc, "extra": extra})

    (MAP_DIR / f"{MAP_NAME}.json").write_text(
        json.dumps({"name": MAP_NAME, "customCoordinates": merged},
                   ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    region_lines = ",\n".join(
        f'    {{ "code": "CA-{prov}", "count": {quotas[prov]} }}'
        for prov in sorted(quotas, key=lambda p: (-quotas[p], p))
    )
    (MAP_DIR / "distribution.json").write_text(
        '{\n  "regions": [\n' + region_lines + "\n  ]\n}\n",
        encoding="utf-8",
    )
    write_point_counts(pools, quotas, new_counts, today)

    print(f"合計 {fmt(len(merged))} 點")
    for prov in sorted(quotas, key=lambda p: (-quotas[p], p)):
        print(f"  {prov} {PROVINCES[prov]}: {fmt(quotas[prov])}(新景 {fmt(new_counts[prov])})")


if __name__ == "__main__":
    main()
