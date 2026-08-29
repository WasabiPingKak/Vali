#!/usr/bin/env python3
"""A County-Balanced Taiwan 平衡縣市的台灣:分配腳本

從 locations/{縣市代碼}.json 點池抽出各縣市配額,產出:
  - {地圖名}.json      合併匯入檔(檔名與 name 欄位取自資料夾名)
  - point-counts.md    點池與配額統計

不產生 distribution.json:行政區分佈由 CasualGuessr 匯入時自動計算。

分配規則:
  - 每個分配單位上限 3,500 點,點池不足者全收(見 CAP)
  - 嘉義縣市、新竹縣市各自合併為一個分配單位共用配額(見 MERGED_UNITS)
  - 手選補點:`A County-Balanced Taiwan_handpick.json` 的點固定併入,加在配額
    之外。這些是望安、七美、吉貝、東引等離島的 Scout(徒步拍攝)街景,Vali
    有一道無條件套用的預設過濾會排除 Scout 與無描述的街景,所以自動流程
    永遠抓不到這些島。該檔案內容固定不再變動,縣市歸屬由 GADM 邊界判定
  - 台灣無陸地邊境,不需鄰國模糊帶過濾
  - 前端相容過濾:剔除 country-coder(CasualGuessr 前端判國套件)TW 多邊形
    外的點,保證上傳後每點都判為台灣
  - 船拍過濾:剔除不在台灣陸地內且離岸超過約 400m 的點;400m 內的
    「離岸」點多是邊界資料精度問題(濱海道路、跨海橋、河中沙洲),保留
  - 抽選走網格輪抽(約 5.5km 網格,跨格輪流取點),避免點位集中在都會區;
    格內新景(2020+)優先,不足配額才用舊景補位
  - 抽選用固定 seed,同輸入重跑結果相同
  - 匯入檔每點在 tags 追加縣市代碼(TW-XXX),方便在地圖編輯器中篩選

邊界資料:
  - scripts/gadm41_TWN_2.json(GADM 4.1 台灣二級行政區,取 22 個縣市聯集
    當陸地範圍)。不用 geoBoundaries 的台灣邊界,它的簡化版漏了東引與綠島,
    會把那些島上的點誤判成船拍點刪掉
  - scripts/country-coder-borders.json(@rapideditor/country-coder 的
    borders.json)。其 TW 多邊形含金門、馬祖、澎湖、蘭嶼、綠島,實測無誤判
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
CAP = 3_500
SEED = 42
NEW_YEAR = 2020  # 新景門檻
OFFSHORE_DEG = 0.004  # 離台灣陸地約 400m 外視為船拍點,剔除
GRID_DEG = 0.05  # 抽選網格邊長,約 5.5km。台灣縣市面積比加拿大省、日本縣
                 # 小一個量級,沿用 11km 網格會讓一個縣市只剩十幾格,打散效果不足

COUNTIES = {
    "TPE": "台北市", "NWT": "新北市", "TAO": "桃園市", "TXG": "台中市",
    "TNN": "台南市", "KHH": "高雄市", "KEE": "基隆市", "HSZ": "新竹市",
    "HSQ": "新竹縣", "CYI": "嘉義市", "CYQ": "嘉義縣", "MIA": "苗栗縣",
    "CHA": "彰化縣", "NAN": "南投縣", "YUN": "雲林縣", "PIF": "屏東縣",
    "ILA": "宜蘭縣", "HUA": "花蓮縣", "TTT": "台東縣", "PEN": "澎湖縣",
    "KIN": "金門縣", "LIE": "連江縣",
}

# 縣市合併為同一個分配單位,共用一份配額。嘉義市被嘉義縣包圍、新竹市除海岸線
# 外被新竹縣包圍,地理上都是同一個生活圈,分家會讓這兩區各佔兩個名額而過重。
# 合併後點池接起來跑同一次網格輪抽,單位內部由地理位置決定分配,不另設權重。
MERGED_UNITS = {
    "嘉義縣市": ["CYQ", "CYI"],
    "新竹縣市": ["HSQ", "HSZ"],
}

HANDPICK_FILE = "A County-Balanced Taiwan_handpick.json"

# GADM 二級行政區的英文名對應到 ISO 3166-2 後綴,用來判手選點的縣市歸屬
GADM_NAME_TO_CODE = {
    "Taipei": "TPE", "NewTaipei": "NWT", "Taoyuan": "TAO", "Taichung": "TXG",
    "Tainan": "TNN", "Kaohsiung": "KHH", "Keelung": "KEE", "HsinchuCity": "HSZ",
    "HsinchuCounty": "HSQ", "ChiayiCity": "CYI", "ChiayiCounty": "CYQ",
    "Miaoli": "MIA", "Changhua": "CHA", "Nantou": "NAN", "Yulin": "YUN",
    "Pingtung": "PIF", "Yilan": "ILA", "Hualien": "HUA", "Taitung": "TTT",
    "Penghu": "PEN", "Kinmen": "KIN", "Lienkiang": "LIE",
}


def build_units() -> list[tuple[str, list[str]]]:
    """回傳 [(單位名, [縣市代碼...])]。未合併的縣市各自成一個單位。"""
    grouped = {code for codes in MERGED_UNITS.values() for code in codes}
    units = [(name, list(codes)) for name, codes in MERGED_UNITS.items()]
    units += [(COUNTIES[c], [c]) for c in COUNTIES if c not in grouped]
    return units


def load_taiwan_land():
    """GADM 二級行政區聯集當台灣陸地範圍(含各離島)。"""
    path = SCRIPTS_DIR / "gadm41_TWN_2.json"
    if not path.exists():
        sys.exit(f"找不到邊界資料 {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return shapely.union_all(
        [shape(f["geometry"]) for f in data["features"] if f.get("geometry")]
    )


def coast_filter(pools: dict[str, list]) -> dict[str, list]:
    """剔除前端判非台灣的點與離岸船拍點,回傳過濾後的點池並列印剔除明細。

    向量化 + prepared geometry:dwithin 含「在多邊形內」的情況
    (境內距離為 0),所以一個判斷式同時涵蓋境內與貼近海岸。
    """
    print("載入邊界資料...", flush=True)
    taiwan = load_taiwan_land()
    cc_borders = json.loads(
        (SCRIPTS_DIR / "country-coder-borders.json").read_text(encoding="utf-8")
    )
    cc_tw = shapely.union_all([
        shape(f["geometry"]) for f in cc_borders["features"]
        if f.get("geometry")
        and (f["properties"].get("iso1A2") == "TW"
             or f["properties"].get("country") == "TW")
    ])
    shapely.prepare(taiwan)
    shapely.prepare(cc_tw)

    filtered = {}
    for co in sorted(pools):
        pool = pools[co]
        pts = shapely.points(
            [loc["lng"] for loc in pool], [loc["lat"] for loc in pool]
        )
        cc_foreign = ~shapely.contains(cc_tw, pts)
        boat = ~shapely.dwithin(taiwan, pts, OFFSHORE_DEG) & ~cc_foreign
        filtered[co] = [
            loc for loc, drop in zip(pool, cc_foreign | boat) if not drop
        ]
        if cc_foreign.any() or boat.any():
            print(
                f"  TW-{co}: 剔除前端判非TW {int(cc_foreign.sum())}、"
                f"船拍/水上 {int(boat.sum())}",
                flush=True,
            )
    return filtered


def dedupe_pools(pools: dict[str, list]) -> dict[str, list]:
    """剔除跨縣市重複的 panoId。

    縣界上的 pano 會同時出現在兩個縣市的 bin 檔,兩邊都抽中就會產生重複點。
    依縣市代碼排序保留第一個,結果穩定。
    """
    seen: set[str] = set()
    result = {}
    dropped = 0
    for code in sorted(pools):
        keep = []
        for loc in pools[code]:
            pano = loc.get("panoId")
            if pano and pano in seen:
                dropped += 1
                continue
            if pano:
                seen.add(pano)
            keep.append(loc)
        result[code] = keep
    if dropped:
        print(f"  剔除跨縣市重複 panoId {dropped} 個", flush=True)
    return result


def load_handpick(existing_pano_ids: set[str]) -> list[tuple[str, dict]]:
    """讀手選補點,判縣市、補上 tags,回傳 [(縣市代碼, 落點)]。

    手選檔是 map-making.app 匯出格式:panoId 可能在頂層也可能在 extra 裡,
    沒有 tags,年份要從 panoDate 取。輸出格式對齊自動流程產的點。
    """
    path = MAP_DIR / HANDPICK_FILE
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    locs = raw["customCoordinates"] if isinstance(raw, dict) else raw

    gadm = json.loads((SCRIPTS_DIR / "gadm41_TWN_2.json").read_text(encoding="utf-8"))
    feats = [
        (GADM_NAME_TO_CODE[f["properties"]["NAME_2"]], shape(f["geometry"]))
        for f in gadm["features"] if f.get("geometry")
    ]
    for _, geom in feats:
        shapely.prepare(geom)

    pts = shapely.points([l["lng"] for l in locs], [l["lat"] for l in locs])
    result = []
    skipped_dup = 0
    for i, loc in enumerate(locs):
        pano = loc.get("panoId") or (loc.get("extra") or {}).get("panoId")
        if pano and pano in existing_pano_ids:
            skipped_dup += 1
            continue
        code = (
            next((c for c, g in feats if shapely.contains(g, pts[i])), None)
            # 邊界資料精度不足時退一步:海岸線 400m 內算進該縣市
            or next((c for c, g in feats if shapely.dwithin(g, pts[i], OFFSHORE_DEG)), None)
        )
        if code is None:
            print(f"  警告:手選點 {loc['lat']:.5f},{loc['lng']:.5f} 判不到縣市,略過")
            continue
        pano_date = (loc.get("extra") or {}).get("panoDate") or ""
        tags = ["TW"]
        if pano_date[:4].isdigit():
            tags.append(pano_date[:4])
        tags += [f"TW-{code}", "Handpick"]
        result.append((code, {
            "lat": loc["lat"],
            "lng": loc["lng"],
            "heading": loc.get("heading", 0),
            "extra": {"tags": tags},
            "panoId": pano,
        }))
    if skipped_dup:
        print(f"  手選點與配額落點重複 {skipped_dup} 個,已略過", flush=True)
    return result


def year(loc) -> int:
    tags = (loc.get("extra") or {}).get("tags") or []
    try:
        return int(tags[1])
    except (IndexError, ValueError):
        return 0


def grid_cell(loc) -> tuple[int, int]:
    """把座標歸進約 5.5km 見方的網格(經度隨緯度收斂,用 cos 補償)。"""
    lat = loc["lat"]
    lng_size = GRID_DEG / max(math.cos(math.radians(lat)), 0.15)
    return int(lat / GRID_DEG), int(loc["lng"] / lng_size)


def select_locations(co: str, pool: list, quota: int) -> list:
    """網格輪抽:點池切網格,跨網格一輪一輪各取一點,直到配額滿。

    均勻隨機抽會讓城市點數等比於街景密度,輪抽把每格點數拉平,
    都會區不再獨佔配額。格內排序為新景(2020+)優先、同組隨機,
    所以每格先貢獻最新的街景。結果維持點池原順序。
    """
    rng = random.Random(f"{SEED}:{co}")
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


def write_point_counts(pools, units, quotas, selected, picked, today):
    total_pool = sum(len(p) for p in pools.values())
    unit_final = {
        name: quotas[name] + sum(picked[c] for c in codes) for name, codes in units
    }
    total_final = sum(unit_final.values())
    total_picked = sum(picked.values())
    lines = [
        f"# {MAP_NAME}:各縣市點位統計",
        "",
        f"更新日期:{today}",
        "策略:`EvenlyByDistanceWithinCountry` + `fixedMinDistance: 100`,"
        "全縣市不框 geojson,輸出鎖定官方 panoId",
        "Filter:`Roads0 gt 2 or ArrowCount gte 3 or ClosestRiver lt 100 "
        "or ClosestRailway lt 100` + 預設 filter(排隧道、壞圖),不看建築密度",
        "海岸過濾:剔除 country-coder(前端判國套件)TW 多邊形外的點,"
        "與離台灣陸地約 400m 外的船拍/水上點(本地 point-in-polygon);"
        "台灣無陸地邊境,不需鄰國模糊帶過濾",
        f"點池總量:**22 縣市 / {fmt(total_pool)} 點**;"
        f"地圖落點:**{fmt(total_final)} 點** / {len(units)} 個分配單位"
        f"(每單位上限 {fmt(CAP)},點池不足者全收)",
        "嘉義縣市、新竹縣市各自合併為一個分配單位共用配額,"
        "點池接起來跑同一次輪抽,單位內部由地理位置決定分配",
        "抽選:約 5.5km 網格輪抽(跨格輪流取點,避免集中都會區),格內新景 2020+ 優先",
        f"手選補點 {fmt(total_picked)} 點加在配額之外,"
        f"來源 `{HANDPICK_FILE}`(內容固定不再變動)",
        "行政區分佈不輸出 distribution.json,由 CasualGuessr 匯入時自動計算",
        "依點池大小排序。",
        "",
        "| 排名 | 分配單位 | 代碼 | 點池 | 配額 | 手選 | 落點 | 佔全圖 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    unit_pool = {name: sum(len(pools[c]) for c in codes) for name, codes in units}
    for rank, (name, codes) in enumerate(
        sorted(units, key=lambda u: (-unit_pool[u[0]], u[0])), 1
    ):
        hp = sum(picked[c] for c in codes)
        code_text = " + ".join(f"TW-{c}" for c in codes)
        lines.append(
            f"| {rank} | {name} | {code_text} | {fmt(unit_pool[name])} "
            f"| {fmt(quotas[name])} | {fmt(hp) if hp else '—'} "
            f"| {fmt(unit_final[name])} | {unit_final[name] / total_final * 100:.2f}% |"
        )

    if total_picked:
        lines += [
            "",
            "## 手選補點",
            "",
            "望安、七美、吉貝、東引等離島只有 Scout(徒步拍攝)街景。Vali 有一道"
            "無條件套用的預設過濾會排除 Scout 與無描述的街景,自動流程永遠抓不到"
            "這些島,因此改用手選檔補上。這些點加在配額之外,縣市歸屬由 GADM 邊界判定,"
            "並在 tags 標記 `Handpick` 方便日後辨識。",
            "",
            "| 縣市 | 代碼 | 手選點數 |",
            "|---|---|---|",
        ]
        for c in sorted(picked, key=lambda c: -picked[c]):
            if picked[c]:
                lines.append(f"| {COUNTIES[c]} | TW-{c} | {fmt(picked[c])} |")

    lines += [
        "",
        "## 合併單位內部分佈",
        "",
        "由網格輪抽決定,不另設權重。市的點數反映其實際規模,不是人工壓低。",
        "",
        "| 單位 | 縣市 | 代碼 | 點池 | 實際落點 | 佔該單位 |",
        "|---|---|---|---|---|---|",
    ]
    for name, codes in units:
        if len(codes) == 1:
            continue
        for c in codes:
            lines.append(
                f"| {name} | {COUNTIES[c]} | TW-{c} | {fmt(len(pools[c]))} "
                f"| {fmt(selected[c])} | {selected[c] / quotas[name] * 100:.1f}% |"
            )
    (MAP_DIR / "point-counts.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    today = date.today().isoformat()
    pools = {}
    for co in COUNTIES:
        pools[co] = json.loads(
            (MAP_DIR / "locations" / f"{co.lower()}.json").read_text(encoding="utf-8")
        )
    pools = dedupe_pools(coast_filter(pools))

    units = build_units()
    quotas = {}
    selected = {c: 0 for c in COUNTIES}
    merged = []
    for name, codes in units:
        # 合併單位:點池接起來當成一個縣市跑輪抽,_county 記住每點的原始縣市,
        # 供 tag 與統計使用(輸出前會拿掉)
        unit_pool = [{**loc, "_county": c} for c in codes for loc in pools[c]]
        quotas[name] = min(len(unit_pool), CAP)
        for loc in select_locations(name, unit_pool, quotas[name]):
            code = loc["_county"]
            selected[code] += 1
            out = {k: v for k, v in loc.items() if k != "_county"}
            extra = dict(loc.get("extra") or {})
            extra["tags"] = list(extra.get("tags") or []) + [f"TW-{code}"]
            out["extra"] = extra
            merged.append(out)

    # 手選補點加在配額之外,不佔用任何單位的配額
    handpick = load_handpick({l.get("panoId") for l in merged if l.get("panoId")})
    picked = {c: 0 for c in COUNTIES}
    for code, loc in handpick:
        picked[code] += 1
        merged.append(loc)

    (MAP_DIR / f"{MAP_NAME}.json").write_text(
        json.dumps({"name": MAP_NAME, "customCoordinates": merged},
                   ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    write_point_counts(pools, units, quotas, selected, picked, today)

    print(f"合計 {fmt(len(merged))} 點 / {len(units)} 個分配單位"
          f"(含手選補點 {fmt(len(handpick))})")
    for name, codes in sorted(units, key=lambda u: (-quotas[u[0]], u[0])):
        extras = []
        if len(codes) > 1:
            extras.append("、".join(f"{COUNTIES[c]} {fmt(selected[c])}" for c in codes))
        hp = sum(picked[c] for c in codes)
        if hp:
            extras.append(f"手選 +{fmt(hp)}")
        detail = "(" + " / ".join(extras) + ")" if extras else ""
        print(f"  {name}: {fmt(quotas[name] + hp)} {detail}")


if __name__ == "__main__":
    main()
