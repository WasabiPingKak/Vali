#!/usr/bin/env python3
"""A Starter World 入門的世界:分配腳本

從 locations/{cc}.json 點池抽出各國配額,產出:
  - final/{cc}.json          各國最終點位
  - A Starter World 入門的世界.json  合併匯入檔(自動點 + 手選點,panoId 去重)
  - point-counts.md          點池與配額統計
  - final-map-countries.md   最終國家清單(含手選歸屬)

分配規則:
  - 總量 40,000 點,以國家為單位盡可能均分
  - 歐洲、亞洲各上限 12,000 點(30%),其餘各洲共享 16,000 點
  - 點池不足配額的國家全給,釋出的配額回流給同組其他國家(water-filling)
  - 每國抽選時新景(2020+)優先,不足配額才用舊景補位
  - locations/ 下 dict 格式({name, customCoordinates})檔案視為手選來源,
    接在自動點後合併,panoId 重複去除

手選點國別歸屬用 Nominatim reverse geocode,結果快取在 handpick-countries.json,
只有快取缺漏且帶 --geocode 參數時才打 API(1 req/s)。

用法:
  python allocate.py            # 用既有快取跑分配
  python allocate.py --geocode  # 快取缺漏的手選點先 geocode 再跑
"""

import json
import random
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

MAP_DIR = Path(__file__).parent
MAP_NAME = MAP_DIR.name
TOTAL_BUDGET = 40_000
EUROPE_BUDGET = 12_000
ASIA_BUDGET = 12_000
CONTINENT_DIRS = ["歐洲", "亞洲", "非洲", "北美洲", "南美洲", "大洋洲"]
FILE_CC = {"uk": "GB"}  # geojson/點池檔名 → ISO country code
CC_FILE = {v: k for k, v in FILE_CC.items()}
HANDPICK_ONLY_CONTINENT = {"EG": "非洲", "CX": "大洋洲", "BM": "北美洲", "CN": "亞洲"}
SEED = 42
NEW_YEAR = 2020  # 新景門檻
CACHE_PATH = MAP_DIR / "handpick-countries.json"


def cc_of(stem: str) -> str:
    return FILE_CC.get(stem, stem.upper())


def load_continents() -> dict[str, str]:
    """從各洲目錄的 geojson 檔名建立 country code → 洲名對照。"""
    mapping = {}
    for cont in CONTINENT_DIRS:
        for f in (MAP_DIR / cont).glob("*.geojson"):
            mapping[cc_of(f.stem)] = cont
    return mapping


def load_names() -> dict[str, str]:
    """從 countries.md 的 `### CC English 中文` 標題取中文國名,去掉括號備註。"""
    names = {"CN": "中國"}  # 防呆:未來若有清單外國家的手選點,至少有名稱可顯示
    pattern = re.compile(r"^### ([A-Z]{2}) .*?(\S+)\s*$")
    for line in (MAP_DIR / "countries.md").read_text(encoding="utf-8").splitlines():
        m = pattern.match(line)
        if m:
            names[m.group(1)] = re.sub(r"（.*", "", m.group(2))
    return names


def load_pools() -> dict[str, list]:
    """讀取裸陣列格式的各國點池。"""
    pools = {}
    for f in (MAP_DIR / "locations").glob("*.json"):
        if not re.fullmatch(r"[a-z]{2}", f.stem):
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(data, list):
            pools[cc_of(f.stem)] = data
    return pools


def load_handpick_files() -> list[tuple[str, list]]:
    """讀取 dict 格式的手選檔,回傳 (檔名, 點列表)。"""
    result = []
    for f in sorted((MAP_DIR / "locations").glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "customCoordinates" in data:
            result.append((f.name, data["customCoordinates"]))
    return result


def water_fill(budget: int, pool_sizes: dict[str, int]) -> dict[str, int]:
    """組內均分配額,點池不足者全給,釋出配額回流,餘數依代碼序 +1。"""
    quotas = {}
    remaining_budget = budget
    uncapped = dict(pool_sizes)
    while uncapped:
        share = remaining_budget // len(uncapped)
        capped = {cc: n for cc, n in uncapped.items() if n <= share}
        if not capped:
            break
        for cc, n in capped.items():
            quotas[cc] = n
            remaining_budget -= n
            del uncapped[cc]
    if uncapped:
        share = remaining_budget // len(uncapped)
        remainder = remaining_budget - share * len(uncapped)
        for i, cc in enumerate(sorted(uncapped)):
            quotas[cc] = share + (1 if i < remainder else 0)
    return quotas


def select_locations(cc: str, pool: list, quota: int) -> list:
    """新景(2020+)優先抽選,不足才用舊景補位;結果維持點池原順序。"""
    def year(loc) -> int:
        tags = (loc.get("extra") or {}).get("tags") or []
        try:
            return int(tags[1])
        except (IndexError, ValueError):
            return 0

    indexed = list(enumerate(pool))
    new = [(i, loc) for i, loc in indexed if year(loc) >= NEW_YEAR]
    old = [(i, loc) for i, loc in indexed if year(loc) < NEW_YEAR]
    rng = random.Random(f"{SEED}:{cc}")
    if len(new) >= quota:
        chosen = rng.sample(new, quota)
    else:
        chosen = new + rng.sample(old, min(quota - len(new), len(old)))
    return [loc for _, loc in sorted(chosen, key=lambda t: t[0])]


def geocode_country(lat: float, lng: float) -> str | None:
    url = (
        "https://nominatim.openstreetmap.org/reverse"
        f"?lat={lat}&lon={lng}&format=jsonv2&zoom=3&accept-language=en"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "starter-world-allocate/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    cc = (data.get("address") or {}).get("country_code")
    return cc.upper() if cc else None


def handpick_key(loc) -> str:
    """快取索引鍵:優先 panoId,無 panoId 的點用座標。"""
    return loc.get("panoId") or f"{loc['lat']:.5f},{loc['lng']:.5f}"


def resolve_handpick_countries(handpick_files, do_geocode: bool) -> dict[str, str]:
    """手選點 → country code,優先用快取,缺漏且 --geocode 時打 Nominatim。

    快取(handpick-countries.json)可手動修正:Nominatim 在國家層級用行政歸屬,
    與這張圖的地區劃分不同時直接改快取值即可(已修正案例:聖誕島 AU→CX、
    香港 CN→HK),重跑不會覆蓋既有項目。
    """
    cache = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    missing = [
        loc for _, locs in handpick_files for loc in locs
        if handpick_key(loc) not in cache
    ]
    if missing and do_geocode:
        for i, loc in enumerate(missing, 1):
            cc = geocode_country(loc["lat"], loc["lng"])
            if cc:
                cache[handpick_key(loc)] = cc
            print(f"  geocode {i}/{len(missing)}: {cc}")
            time.sleep(1.1)
        CACHE_PATH.write_text(
            json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    elif missing:
        print(f"警告:{len(missing)} 個手選點不在快取,國別歸屬記為 ??(用 --geocode 補)")
    return cache


def fmt(n: int) -> str:
    return f"{n:,}"


def write_point_counts(pools, quotas, names, continents, group_of, today):
    """重產 point-counts.md。"""
    total_pool = sum(len(p) for p in pools.values())
    # 各組未封頂國家的均分基準值(顯示用)
    base = {}
    for group in ("歐洲", "亞洲", "其他洲"):
        ccs = [cc for cc in pools if group_of[cc] == group]
        uncapped = [cc for cc in ccs if quotas[cc] < len(pools[cc])]
        base[group] = min((quotas[cc] for cc in uncapped), default=0)
    lines = [
        f"# {MAP_NAME}:各國點位統計",
        "",
        f"更新日期:{today}",
        "策略:`EvenlyByDistanceWithinCountry` + `fixedMinDistance: 100`,輸出鎖定官方 panoId",
        f"點池總量:**{len(pools)} 國 / {fmt(total_pool)} 點**;"
        f"地圖配額:**{fmt(TOTAL_BUDGET)} 點**(歐洲、亞洲各鎖 30%)+ 手選點",
        f"配額均等值:歐洲 {base['歐洲']} 點/國,亞洲 {base['亞洲']} 點/國,"
        f"其他洲 {base['其他洲']} 點/國(點池不足者全給)",
        "",
        "手選國家(不用程式跑):EG 埃及、CX 聖誕島、BM 百慕達、BR 的巴西利亞(城市)",
        "已移除:MP 北馬里亞納群島",
    ]
    for cont in CONTINENT_DIRS:
        ccs = [cc for cc in pools if continents[cc] == cont]
        cont_quota = sum(quotas[cc] for cc in ccs)
        lines += [
            "",
            f"## {cont}({len(ccs)} 國,配額 {fmt(cont_quota)} 點,"
            f"佔 {cont_quota / TOTAL_BUDGET * 100:.1f}%)",
            "",
            "| 代碼 | 國家 | 點池 | 配額 | 佔全部 | 佔本洲 |",
            "|---|---|---|---|---|---|",
        ]
        for cc in sorted(ccs, key=lambda c: (-quotas[c], c)):
            q = quotas[cc]
            lines.append(
                f"| {cc} | {names.get(cc, cc)} | {fmt(len(pools[cc]))} | {fmt(q)} "
                f"| {q / TOTAL_BUDGET * 100:.2f}% "
                f"| {q / cont_quota * 100:.1f}% |"
            )
    (MAP_DIR / "point-counts.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_final_map_countries(auto_counts, handpick_counts, names, continents, grand, today):
    """重產 final-map-countries.md。"""
    all_ccs = set(auto_counts) | set(handpick_counts)
    lines = [
        f"# {MAP_NAME}:最終國家清單",
        "",
        f"快照日期:{today};對應匯入檔 `{MAP_NAME}.json`(**{fmt(grand)} 點**)",
        "點數 = 自動配額 + 手選點(地標與手選國家)。百分比為佔全地圖比例。",
    ]
    for cont in CONTINENT_DIRS:
        ccs = [cc for cc in all_ccs
               if continents.get(cc, HANDPICK_ONLY_CONTINENT.get(cc)) == cont]
        totals = {cc: auto_counts.get(cc, 0) + handpick_counts.get(cc, 0) for cc in ccs}
        cont_total = sum(totals.values())
        lines += [
            "",
            f"## {cont}({len(ccs)} 國,{fmt(cont_total)} 點,{cont_total / grand * 100:.1f}%)",
            "",
            "| 代碼 | 國家 | 自動 | 手選 | 合計 | 佔比 |",
            "|---|---|---|---|---|---|",
        ]
        for cc in sorted(ccs, key=lambda c: (-totals[c], c)):
            lines.append(
                f"| {cc} | {names.get(cc, cc)} | {auto_counts.get(cc, 0)} "
                f"| {handpick_counts.get(cc, 0)} | {totals[cc]} "
                f"| {totals[cc] / grand * 100:.2f}% |"
            )
    unknown = handpick_counts.get("??", 0)
    if unknown:
        lines += ["", f"註:{unknown} 個手選點國別未歸屬(跑 `--geocode` 後重產)。"]
    unmapped = sorted(
        cc for cc in all_ccs
        if cc != "??" and cc not in continents and cc not in HANDPICK_ONLY_CONTINENT
    )
    if unmapped:
        lines += ["", f"註:{'、'.join(unmapped)} 無洲別歸屬,未列入上表,"
                      f"請在 allocate.py 的 HANDPICK_ONLY_CONTINENT 補上。"]
        print(f"警告:{unmapped} 無洲別歸屬,manifest 未列入")
    (MAP_DIR / "final-map-countries.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    do_geocode = "--geocode" in sys.argv
    today = date.today().isoformat()

    continents = load_continents()
    names = load_names()
    pools = load_pools()
    missing = set(pools) - set(continents)
    if missing:
        sys.exit(f"錯誤:找不到洲別歸屬的點池 {sorted(missing)}")

    # 歐、亞獨立計算,其餘各洲併為一組共享預算
    group_of = {
        cc: cont if cont in ("歐洲", "亞洲") else "其他洲"
        for cc, cont in continents.items()
    }
    quotas = {}
    for group, budget in [
        ("歐洲", EUROPE_BUDGET),
        ("亞洲", ASIA_BUDGET),
        ("其他洲", TOTAL_BUDGET - EUROPE_BUDGET - ASIA_BUDGET),
    ]:
        sizes = {cc: len(pool) for cc, pool in pools.items() if group_of[cc] == group}
        quotas.update(water_fill(budget, sizes))

    # 抽選並輸出 final/{cc}.json
    final_dir = MAP_DIR / "final"
    final_dir.mkdir(exist_ok=True)
    auto_counts = {}
    merged = []
    for cc in sorted(pools):
        chosen = select_locations(cc, pools[cc], quotas[cc])
        auto_counts[cc] = len(chosen)
        stem = CC_FILE.get(cc, cc.lower())
        (final_dir / f"{stem}.json").write_text(
            json.dumps(chosen, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        merged.extend(chosen)

    # 手選點接在自動點後面,panoId 重複去除
    handpick_files = load_handpick_files()
    handpick_cc = resolve_handpick_countries(handpick_files, do_geocode)
    seen = {loc["panoId"] for loc in merged if loc.get("panoId")}
    handpick_counts = {}
    for _, locs in handpick_files:
        for loc in locs:
            pid = loc.get("panoId")
            if pid and pid in seen:
                continue
            if pid:
                seen.add(pid)
            cc = handpick_cc.get(handpick_key(loc), "??")
            # 補上與自動點一致的 tags([國別, 年份]),年份取自 panoDate,
            # 另加 handpick 標記方便在地圖編輯器中篩選;只寫進匯入檔,不動手選原檔
            year = ((loc.get("extra") or {}).get("panoDate") or "")[:4]
            extra = dict(loc.get("extra") or {})
            extra["tags"] = [t for t in (cc if cc != "??" else "", year) if t]
            extra["tags"].append("handpick")
            merged.append({**loc, "extra": extra})
            handpick_counts[cc] = handpick_counts.get(cc, 0) + 1

    (MAP_DIR / f"{MAP_NAME}.json").write_text(
        json.dumps({"name": MAP_NAME, "customCoordinates": merged},
                   ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    write_point_counts(pools, quotas, names, continents, group_of, today)
    write_final_map_countries(auto_counts, handpick_counts, names, continents,
                              len(merged), today)

    auto_total = sum(auto_counts.values())
    print(f"自動配額 {fmt(auto_total)} 點 + 手選 {fmt(len(merged) - auto_total)} 點"
          f" = {fmt(len(merged))} 點")
    for group in ("歐洲", "亞洲", "其他洲"):
        s = sum(q for cc, q in quotas.items() if group_of[cc] == group)
        print(f"  {group}: {fmt(s)}")


if __name__ == "__main__":
    main()
