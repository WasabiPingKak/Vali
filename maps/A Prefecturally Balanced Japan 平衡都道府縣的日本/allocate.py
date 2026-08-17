#!/usr/bin/env python3
"""A Prefecturally Balanced Japan 平衡都道府縣的日本:分配腳本

從 locations/jp-{縣代碼}.json 點池抽出各縣配額,產出:
  - {地圖名}.json      合併匯入檔(檔名與 name 欄位取自資料夾名)
  - point-counts.md    點池與配額統計

不再產生 distribution.json:行政區分佈改由 CasualGuessr 匯入時自動計算。

分配規則:
  - 每縣 2,000 點(每縣點池都遠超過配額,無不足問題)
  - 日本無陸地邊境,不需做加拿大的鄰國模糊帶過濾
  - 前端相容過濾:剔除 country-coder(CasualGuessr 前端判國套件)JP 多邊形
    外的點,保證上傳後每點都判為日本
  - 船拍過濾:剔除不在日本陸地內且離岸超過約 400m 的點(渡輪、港灣水上
    coverage 會過 ClosestRiver filter);400m 內的「離岸」點多是邊界資料
    精度問題(沿海道路、跨海橋、河中島),保留
  - 抽選走網格輪抽(約 11km 網格,跨格輪流取點),避免點位集中在都會區;
    格內新景(2020+)優先,不足配額才用舊景補位
  - 抽選用固定 seed,同輸入重跑結果相同
  - 匯入檔每點在 tags 追加縣代碼(JP-XX),方便在地圖編輯器中篩選

邊界資料:scripts/geoBoundaries-JPN-ADM0.geojson(geoBoundaries gbOpen,
來源日本國土交通省國土數值情報;GADM 站台連不上時的替代來源,精度相當)、
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

# Windows 主控台預設 cp950 印不出「栃」等字,避免統計印到一半崩潰
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAP_DIR = Path(__file__).parent
MAP_NAME = MAP_DIR.name
SCRIPTS_DIR = MAP_DIR.parent.parent / "scripts"
CAP = 2_000
SEED = 42
NEW_YEAR = 2020  # 新景門檻
OFFSHORE_DEG = 0.004  # 離日本陸地約 400m 外視為船拍點,剔除
GRID_DEG = 0.1  # 抽選網格邊長,約 11km

PREFECTURES = {
    "01": "北海道", "02": "青森", "03": "岩手", "04": "宮城", "05": "秋田",
    "06": "山形", "07": "福島", "08": "茨城", "09": "栃木", "10": "群馬",
    "11": "埼玉", "12": "千葉", "13": "東京", "14": "神奈川", "15": "新潟",
    "16": "富山", "17": "石川", "18": "福井", "19": "山梨", "20": "長野",
    "21": "岐阜", "22": "靜岡", "23": "愛知", "24": "三重", "25": "滋賀",
    "26": "京都", "27": "大阪", "28": "兵庫", "29": "奈良", "30": "和歌山",
    "31": "鳥取", "32": "島根", "33": "岡山", "34": "廣島", "35": "山口",
    "36": "德島", "37": "香川", "38": "愛媛", "39": "高知", "40": "福岡",
    "41": "佐賀", "42": "長崎", "43": "熊本", "44": "大分", "45": "宮崎",
    "46": "鹿兒島", "47": "沖繩",
}


def load_boundary(name: str):
    path = SCRIPTS_DIR / name
    if not path.exists():
        sys.exit(
            f"找不到邊界資料 {path},下載連結可從 geoBoundaries API 取得:\n"
            f"https://www.geoboundaries.org/api/current/gbOpen/JPN/ADM0/"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return shape(data["features"][0]["geometry"])


def coast_filter(pools: dict[str, list]) -> dict[str, list]:
    """剔除前端判非日本的點與離岸船拍點,回傳過濾後的點池並列印剔除明細。

    向量化 + prepared geometry:dwithin 含「在多邊形內」的情況
    (境內距離為 0),所以一個判斷式同時涵蓋境內與貼近海岸。
    """
    print("載入邊界資料...", flush=True)
    japan = load_boundary("geoBoundaries-JPN-ADM0.geojson")
    cc_borders = json.loads(
        (SCRIPTS_DIR / "country-coder-borders.json").read_text(encoding="utf-8")
    )
    cc_jp = shape(
        next(f["geometry"] for f in cc_borders["features"]
             if f["properties"].get("iso1A2") == "JP")
    )
    shapely.prepare(japan)
    shapely.prepare(cc_jp)

    filtered = {}
    for pref in sorted(pools):
        pool = pools[pref]
        pts = shapely.points(
            [loc["lng"] for loc in pool], [loc["lat"] for loc in pool]
        )
        cc_foreign = ~shapely.contains(cc_jp, pts)
        boat = ~shapely.dwithin(japan, pts, OFFSHORE_DEG) & ~cc_foreign
        filtered[pref] = [
            loc for loc, drop in zip(pool, cc_foreign | boat) if not drop
        ]
        if cc_foreign.any() or boat.any():
            print(
                f"  JP-{pref}: 剔除前端判非JP {int(cc_foreign.sum())}、"
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


def select_locations(pref: str, pool: list, quota: int) -> list:
    """網格輪抽:點池切網格,跨網格一輪一輪各取一點,直到配額滿。

    均勻隨機抽會讓城市點數等比於街景密度,輪抽把每格點數拉平,
    都會區不再獨佔配額。格內排序為新景(2020+)優先、同組隨機,
    所以每格先貢獻最新的街景。結果維持點池原順序。
    """
    rng = random.Random(f"{SEED}:{pref}")
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
        f"# {MAP_NAME}:各都道府縣點位統計",
        "",
        f"更新日期:{today}",
        "策略:`EvenlyByDistanceWithinCountry` + `fixedMinDistance: 100`,"
        "全縣不框 geojson,輸出鎖定官方 panoId",
        "Filter:`Roads0 gt 2 or ArrowCount gte 3 or ClosestRiver lt 100 "
        "or ClosestRailway lt 100` + 預設 filter(排隧道、壞圖),不看建築密度",
        "海岸過濾:剔除 country-coder(前端判國套件)JP 多邊形外的點,"
        "與離日本陸地約 400m 外的船拍/水上點(本地 point-in-polygon);"
        "日本無陸地邊境,不需鄰國模糊帶過濾",
        f"點池總量:**47 都道府縣 / {fmt(total_pool)} 點**;"
        f"地圖配額:**{fmt(total_quota)} 點**(每縣 {fmt(CAP)})",
        "抽選:約 11km 網格輪抽(跨格輪流取點,避免集中都會區),格內新景 2020+ 優先",
        "行政區分佈不再輸出 distribution.json,由 CasualGuessr 匯入時自動計算",
        "依點池大小排序。",
        "",
        "| 排名 | 代碼 | 都道府縣 | 點池 | 配額 | 佔全圖 |",
        "|---|---|---|---|---|---|",
    ]
    order = sorted(pools, key=lambda p: (-len(pools[p]), p))
    for rank, pref in enumerate(order, 1):
        q = quotas[pref]
        lines.append(
            f"| {rank} | JP-{pref} | {PREFECTURES[pref]} | {fmt(len(pools[pref]))} "
            f"| {fmt(q)} | {q / total_quota * 100:.2f}% |"
        )
    (MAP_DIR / "point-counts.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    today = date.today().isoformat()
    pools = {}
    for pref in PREFECTURES:
        pools[pref] = json.loads(
            (MAP_DIR / "locations" / f"jp-{pref}.json").read_text(encoding="utf-8")
        )
    pools = coast_filter(pools)

    quotas = {pref: min(len(pool), CAP) for pref, pool in pools.items()}
    merged = []
    for pref in sorted(pools):
        chosen = select_locations(pref, pools[pref], quotas[pref])
        for loc in chosen:
            extra = dict(loc.get("extra") or {})
            extra["tags"] = list(extra.get("tags") or []) + [f"JP-{pref}"]
            merged.append({**loc, "extra": extra})

    (MAP_DIR / f"{MAP_NAME}.json").write_text(
        json.dumps({"name": MAP_NAME, "customCoordinates": merged},
                   ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    write_point_counts(pools, quotas, today)

    print(f"合計 {fmt(len(merged))} 點")
    for pref in sorted(quotas):
        print(f"  JP-{pref} {PREFECTURES[pref]}: {fmt(quotas[pref])}")


if __name__ == "__main__":
    main()
