#!/usr/bin/env python3
"""A District-Balanced Hong Kong 平衡行政區的香港:分配腳本

從 locations/hk-{區代碼}.json 點池抽出各區配額,產出:
  - {地圖名}.json      合併匯入檔(檔名與 name 欄位取自資料夾名)
  - point-counts.md    點池與配額統計

分配規則:
  - 統一 cap 600:池 >= 600 的區壓到 600,其餘全收
  - 需要壓縮的區用網格輪抽(約 550m 網格,跨格輪流取點)避免抽到一整片
    相鄰街廓;格內新景(2020+)優先,不足配額才用舊景補位
  - 不做邊境與船拍過濾:HK+CN-HK.bin 資料本身就限 HK,官方 coverage 不會
    有中國/澳門的點,且 fixedMinDistance:100 + globalLocationFilter 已在
    Vali 端擋掉大部分水上點
  - 抽選用固定 seed,同輸入重跑結果相同
  - 匯入檔每點在 tags 追加區代碼(HK-XX,對應 GADM HASC_2),方便在地圖
    編輯器中篩選

邊界資料:scripts/gadm41_HKG_2.json(18 區 ADM2)產出的
  geojson/hk-{區}.geojson(每區獨立 FeatureCollection),Vali 端 include-only。

用法:
  python allocate.py
"""

import json
import random
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAP_DIR = Path(__file__).parent
MAP_NAME = MAP_DIR.name
SEED = 42
NEW_YEAR = 2020
GRID_DEG = 0.005  # 抽選網格邊長,約 550m(HK 小,用 Japan 的 1/20)

# slug -> (tag code, 中文名)。tag code 對應 GADM HASC_2 (HK.XX -> HK-XX)
DISTRICTS = {
    "cw": ("HK-CW", "中西區"),
    "ea": ("HK-EA", "東區"),
    "is": ("HK-IS", "離島區"),
    "kc": ("HK-KC", "九龍城區"),
    "ki": ("HK-KI", "葵青區"),
    "ku": ("HK-KU", "觀塘區"),
    "no": ("HK-NO", "北區"),
    "sk": ("HK-SK", "西貢區"),
    "st": ("HK-ST", "沙田區"),
    "ss": ("HK-SS", "深水埗區"),
    "so": ("HK-SO", "南區"),
    "tp": ("HK-TP", "大埔區"),
    "tw": ("HK-TW", "荃灣區"),
    "tm": ("HK-TM", "屯門區"),
    "wc": ("HK-WC", "灣仔區"),
    "wt": ("HK-WT", "黃大仙區"),
    "yt": ("HK-YT", "油尖旺區"),
    "yl": ("HK-YL", "元朗區"),
}

# 統一 cap:所有區都 min(pool, CAP)。>= CAP 的區才會壓縮,其他全收。
CAP = 600


def year(loc) -> int:
    tags = (loc.get("extra") or {}).get("tags") or []
    try:
        return int(tags[1])
    except (IndexError, ValueError):
        return 0


def grid_cell(loc) -> tuple[int, int]:
    """把座標歸進網格。HK 緯度 ~22.3,cos ~0.925,經度差不多,直接用同一格距。"""
    return int(loc["lat"] / GRID_DEG), int(loc["lng"] / GRID_DEG)


def select_locations(slug: str, pool: list, quota: int) -> list:
    """網格輪抽:點池切網格,跨網格一輪一輪各取一點,直到配額滿。

    配額 >= 池大小時直接回傳整池;需要壓縮時才動用網格輪抽,避免同一片
    街廓被連續採樣。格內排序為新景(2020+)優先、同組隨機。結果維持點池
    原順序,匯入時 GeoGuessr 編輯器會照順序顯示。
    """
    if quota >= len(pool):
        return list(pool)

    rng = random.Random(f"{SEED}:{slug}")
    buckets: dict[tuple[int, int], list] = {}
    for i, loc in enumerate(pool):
        buckets.setdefault(grid_cell(loc), []).append((i, loc))
    for b in buckets.values():
        b.sort(key=lambda t: (year(t[1]) >= NEW_YEAR, rng.random()), reverse=True)

    keys = sorted(buckets)
    rng.shuffle(keys)

    chosen, round_i = [], 0
    while len(chosen) < quota:
        progressed = False
        for k in keys:
            if round_i < len(buckets[k]):
                chosen.append(buckets[k][round_i])
                progressed = True
                if len(chosen) >= quota:
                    break
        if not progressed:
            break
        round_i += 1
    return [loc for _, loc in sorted(chosen, key=lambda t: t[0])]


def fmt(n: int) -> str:
    return f"{n:,}"


def write_point_counts(pools, quotas, today):
    total_pool = sum(len(p) for p in pools.values())
    total_quota = sum(quotas.values())
    lines = [
        f"# {MAP_NAME}:各區點位統計",
        "",
        f"更新日期:{today}",
        "策略:`EvenlyByDistanceWithinCountry` + `fixedMinDistance: 25`,"
        "每區用 GADM 4.1 HKG ADM2 邊界(HASC_2)geojson 圈範圍",
        "Filter:`Roads0 gt 2 or ArrowCount gte 3 or ClosestRiver lt 100 "
        "or ClosestRailway lt 100` + 預設 filter(排隧道、壞圖)",
        f"配額規則:統一 cap {fmt(CAP)},池 >= {fmt(CAP)} 的區壓下來,"
        "小於的全收",
        f"點池總量:**18 區 / {fmt(total_pool)} 點**;"
        f"地圖配額:**{fmt(total_quota)} 點**",
        "抽選:池 >= cap 的區用約 550m 網格輪抽(跨格輪流取點,避免集中一片街廓),"
        "格內新景 2020+ 優先;其他區不動,整池收進",
        "行政區分佈由 CasualGuessr 匯入時自動計算,不再輸出 distribution.json",
        "依配額大小排序。",
        "",
        "| 排名 | 代碼 | 區 | 點池 | 配額 | 佔全圖 |",
        "|---|---|---|---|---|---|",
    ]
    order = sorted(pools, key=lambda p: (-quotas[p], -len(pools[p]), p))
    for rank, slug in enumerate(order, 1):
        tag, cname = DISTRICTS[slug]
        q = quotas[slug]
        lines.append(
            f"| {rank} | {tag} | {cname} | {fmt(len(pools[slug]))} "
            f"| {fmt(q)} | {q / total_quota * 100:.2f}% |"
        )
    (MAP_DIR / "point-counts.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    today = date.today().isoformat()
    pools = {}
    for slug in DISTRICTS:
        p = MAP_DIR / "locations" / f"hk-{slug}.json"
        if not p.exists():
            sys.exit(f"缺少點池 {p},請先跑 run-all.sh")
        pools[slug] = json.loads(p.read_text(encoding="utf-8"))

    quotas = {slug: min(len(pool), CAP) for slug, pool in pools.items()}

    merged = []
    for slug in DISTRICTS:
        tag, _ = DISTRICTS[slug]
        chosen = select_locations(slug, pools[slug], quotas[slug])
        for loc in chosen:
            extra = dict(loc.get("extra") or {})
            extra["tags"] = list(extra.get("tags") or []) + [tag]
            merged.append({**loc, "extra": extra})

    (MAP_DIR / f"{MAP_NAME}.json").write_text(
        json.dumps(
            {"name": MAP_NAME, "customCoordinates": merged},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    write_point_counts(pools, quotas, today)

    print(f"合計 {fmt(len(merged))} 點")
    for slug in DISTRICTS:
        tag, cname = DISTRICTS[slug]
        print(
            f"  {tag} {cname}: {fmt(quotas[slug])}"
            + (
                f" (壓縮自 {fmt(len(pools[slug]))})"
                if quotas[slug] < len(pools[slug])
                else ""
            )
        )


if __name__ == "__main__":
    main()
