#!/usr/bin/env python3
"""World's Biggest Cities 各國最大城市:分配腳本

從 locations/{cc}.json 點池抽出各國配額,產出:
  - final/{cc}.json                    各國最終點位
  - World's Biggest Cities 各國最大城市.json  合併匯入檔
  - point-counts.md                    點池與配額統計

分配規則:
  - 其他洲每國上限 250 點,歐洲、亞洲各佔 30%(預算由其他洲總量反推)
  - 組內以國家為單位盡可能均分(water-filling)
  - 新景(2020+)優先,不足配額才用舊景補位
  - 抽選用固定 seed,同輸入重跑結果相同
"""

import json
import random
import re
import sys
from datetime import date
from pathlib import Path

MAP_DIR = Path(__file__).parent
MAP_NAME = MAP_DIR.name
OTHER_CAP = 250  # 其他洲每國上限
EUROPE_RATIO = 0.30
ASIA_RATIO = 0.30
CONTINENT_DIRS = ["歐洲", "亞洲", "非洲", "北美洲", "南美洲", "大洋洲"]
FILE_CC = {"uk": "GB"}
CC_FILE = {v: k for k, v in FILE_CC.items()}
SEED = 42
NEW_YEAR = 2020

COUNTRY_NAMES = {
    "AD": "安道爾", "AL": "阿爾巴尼亞", "AT": "奧地利", "BA": "波赫",
    "BE": "比利時", "BG": "保加利亞", "CH": "瑞士", "CY": "賽普勒斯",
    "CZ": "捷克", "DE": "德國", "DK": "丹麥", "EE": "愛沙尼亞",
    "ES": "西班牙", "FI": "芬蘭", "FO": "法羅群島", "FR": "法國",
    "GB": "英國", "GR": "希臘", "HR": "克羅埃西亞", "HU": "匈牙利",
    "IE": "愛爾蘭", "IS": "冰島", "IT": "義大利", "LI": "列支敦士登",
    "LT": "立陶宛", "LU": "盧森堡", "LV": "拉脫維亞", "MC": "摩納哥",
    "ME": "蒙特內哥羅", "MK": "北馬其頓", "MT": "馬爾他", "NL": "荷蘭",
    "NO": "挪威", "PL": "波蘭", "PT": "葡萄牙", "RO": "羅馬尼亞",
    "RS": "塞爾維亞", "RU": "俄羅斯", "SE": "瑞典", "SI": "斯洛維尼亞",
    "SK": "斯洛伐克", "SM": "聖馬利諾", "UA": "烏克蘭", "XK": "科索沃",
    "AE": "阿拉伯聯合大公國", "BD": "孟加拉", "BT": "不丹", "GE": "喬治亞",
    "HK": "香港", "ID": "印尼", "IL": "以色列", "IN": "印度",
    "JO": "約旦", "JP": "日本", "KG": "吉爾吉斯", "KH": "柬埔寨",
    "KR": "南韓", "KZ": "哈薩克", "LA": "寮國", "LB": "黎巴嫩",
    "LK": "斯里蘭卡", "MN": "蒙古", "MO": "澳門", "MY": "馬來西亞",
    "NP": "尼泊爾", "OM": "阿曼", "PH": "菲律賓", "PS": "巴勒斯坦",
    "QA": "卡達", "SG": "新加坡", "TH": "泰國", "TR": "土耳其",
    "TW": "台灣", "VN": "越南",
    "CA": "加拿大", "CR": "哥斯大黎加", "CW": "庫拉索", "DO": "多明尼加",
    "GL": "格陵蘭", "GT": "瓜地馬拉", "GU": "關島", "MX": "墨西哥",
    "PA": "巴拿馬", "PR": "波多黎各", "US": "美國",
    "AR": "阿根廷", "BO": "玻利維亞", "BR": "巴西", "CL": "智利",
    "CO": "哥倫比亞", "EC": "厄瓜多", "PE": "秘魯", "PY": "巴拉圭",
    "UY": "烏拉圭",
    "AU": "澳洲", "NZ": "紐西蘭",
    "BW": "波札那", "GH": "迦納", "KE": "肯亞", "LS": "賴索托",
    "NA": "納米比亞", "NG": "奈及利亞", "RE": "留尼旺", "RW": "盧安達",
    "SN": "塞內加爾", "ST": "聖多美普林西比", "SZ": "史瓦帝尼",
    "TN": "突尼西亞", "UG": "烏干達", "ZA": "南非",
}

CITY_NAMES = {
    "AD": "安道爾城 Andorra la Vella", "AL": "地拉那 Tirana",
    "AT": "維也納 Vienna", "BA": "塞拉耶佛 Sarajevo",
    "BE": "布魯塞爾 Brussels", "BG": "索菲亞 Sofia",
    "CH": "蘇黎世 Zürich", "CY": "尼古西亞 Nicosia",
    "CZ": "布拉格 Prague", "DE": "柏林 Berlin",
    "DK": "哥本哈根 Copenhagen", "EE": "塔林 Tallinn",
    "ES": "馬德里 Madrid", "FI": "赫爾辛基 Helsinki",
    "FO": "托爾斯港 Tórshavn", "FR": "巴黎 Paris",
    "GB": "倫敦 London", "GR": "雅典 Athens",
    "HR": "札格瑞布 Zagreb", "HU": "布達佩斯 Budapest",
    "IE": "都柏林 Dublin", "IS": "雷克雅維克 Reykjavik",
    "IT": "羅馬 Rome", "LI": "瓦都茲 Vaduz",
    "LT": "維爾紐斯 Vilnius", "LU": "盧森堡 Luxembourg",
    "LV": "里加 Riga", "MC": "摩納哥 Monaco",
    "ME": "波德戈里察 Podgorica", "MK": "史高比耶 Skopje",
    "MT": "瓦萊塔 Valletta", "NL": "阿姆斯特丹 Amsterdam",
    "NO": "奧斯陸 Oslo", "PL": "華沙 Warsaw",
    "PT": "里斯本 Lisbon", "RO": "布加勒斯特 Bucharest",
    "RS": "貝爾格勒 Belgrade", "RU": "莫斯科 Moscow",
    "SE": "斯德哥爾摩 Stockholm", "SI": "盧比安納 Ljubljana",
    "SK": "布拉提斯拉瓦 Bratislava", "SM": "聖馬利諾 San Marino",
    "UA": "基輔 Kyiv", "XK": "普里斯提納 Pristina",
    "AE": "杜拜 Dubai", "BD": "達卡 Dhaka",
    "BT": "廷布 Thimphu", "GE": "提比里斯 Tbilisi",
    "HK": "香港 Hong Kong", "ID": "雅加達 Jakarta",
    "IL": "特拉維夫 Tel Aviv", "IN": "新德里 Delhi",
    "JO": "安曼 Amman", "JP": "東京 Tokyo",
    "KG": "比什凱克 Bishkek", "KH": "金邊 Phnom Penh",
    "KR": "首爾 Seoul", "KZ": "阿斯塔納 Astana",
    "LA": "永珍 Vientiane", "LB": "貝魯特 Beirut",
    "LK": "可倫坡 Colombo", "MN": "烏蘭巴托 Ulaanbaatar",
    "MO": "澳門 Macau", "MY": "吉隆坡 Kuala Lumpur",
    "NP": "加德滿都 Kathmandu", "OM": "馬斯喀特 Muscat",
    "PH": "馬尼拉 Manila", "PS": "拉姆安拉 Ramallah",
    "QA": "杜哈 Doha", "SG": "新加坡 Singapore",
    "TH": "曼谷 Bangkok", "TR": "伊斯坦堡 Istanbul",
    "TW": "台北 Taipei", "VN": "河內 Hanoi",
    "CA": "多倫多 Toronto", "CR": "聖荷西 San José",
    "CW": "威廉斯塔德 Willemstad", "DO": "聖多明哥 Santo Domingo",
    "GL": "努克 Nuuk", "GT": "瓜地馬拉市 Guatemala City",
    "GU": "阿加尼亞 Hagåtña", "MX": "墨西哥城 Mexico City",
    "PA": "巴拿馬城 Panama City", "PR": "聖胡安 San Juan",
    "US": "紐約 New York",
    "AR": "布宜諾斯艾利斯 Buenos Aires", "BO": "拉巴斯 La Paz",
    "BR": "聖保羅 São Paulo", "CL": "聖地亞哥 Santiago",
    "CO": "波哥大 Bogotá", "EC": "基多 Quito",
    "PE": "利馬 Lima", "PY": "亞松森 Asunción",
    "UY": "蒙特維多 Montevideo",
    "AU": "雪梨 Sydney", "NZ": "威靈頓 Wellington",
    "BW": "嘉柏隆里 Gaborone", "GH": "阿克拉 Accra",
    "KE": "奈洛比 Nairobi", "LS": "馬塞魯 Maseru",
    "NA": "溫得和克 Windhoek", "NG": "拉各斯 Lagos",
    "RE": "聖但尼 Saint-Denis", "RW": "吉佳利 Kigali",
    "SN": "達喀爾 Dakar", "ST": "聖多美 São Tomé",
    "SZ": "曼乙尼 Manzini", "TN": "突尼斯 Tunis",
    "UG": "坎帕拉 Kampala", "ZA": "約翰尼斯堡 Johannesburg",
}


def cc_of(stem: str) -> str:
    return FILE_CC.get(stem, stem.upper())


def load_continents() -> dict[str, str]:
    mapping = {}
    for cont in CONTINENT_DIRS:
        for f in (MAP_DIR / cont).glob("*.geojson"):
            mapping[cc_of(f.stem)] = cont
    return mapping


def load_pools() -> dict[str, list]:
    pools = {}
    for f in (MAP_DIR / "locations").glob("*.json"):
        if not re.fullmatch(r"[a-z]{2}", f.stem):
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(data, list):
            pools[cc_of(f.stem)] = data
    return pools


def water_fill(budget: int, pool_sizes: dict[str, int],
               max_per_country: int | None = None) -> dict[str, int]:
    """組內均分配額,點池不足者全給,釋出配額回流,餘數依代碼序 +1。
    max_per_country: 每國硬上限(即使預算充足也不超過此值)。"""
    quotas = {}
    remaining_budget = budget
    uncapped = dict(pool_sizes)
    while uncapped:
        share = remaining_budget // len(uncapped)
        if max_per_country is not None:
            share = min(share, max_per_country)
        capped = {cc: n for cc, n in uncapped.items()
                  if n <= share or (max_per_country and n >= max_per_country)}
        if not capped:
            break
        for cc in sorted(capped):
            n = min(capped[cc], max_per_country) if max_per_country else capped[cc]
            quotas[cc] = n
            remaining_budget -= n
            del uncapped[cc]
    if uncapped:
        share = remaining_budget // len(uncapped)
        if max_per_country is not None:
            share = min(share, max_per_country)
        used = share * len(uncapped)
        remainder = min(remaining_budget - used, len(uncapped))
        for i, cc in enumerate(sorted(uncapped)):
            quotas[cc] = share + (1 if i < remainder else 0)
    return quotas


def select_locations(cc: str, pool: list, quota: int) -> list:
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


def fmt(n: int) -> str:
    return f"{n:,}"


def write_point_counts(pools, quotas, continents, group_of, total_budget, today):
    total_pool = sum(len(p) for p in pools.values())
    total_quota = sum(quotas.values())
    base = {}
    for group in ("歐洲", "亞洲", "其他洲"):
        ccs = [cc for cc in pools if group_of[cc] == group]
        uncapped = [cc for cc in ccs if quotas[cc] < len(pools[cc])]
        base[group] = min((quotas[cc] for cc in uncapped), default=0)
    lines = [
        f"# {MAP_NAME}:各國點位統計",
        "",
        f"更新日期:{today}",
        "策略:EvenlyByDistanceWithinCountry + fixedMinDistance: 100",
        f"點池總量:**{len(pools)} 國 / {fmt(total_pool)} 點**;"
        f"地圖配額:**{fmt(total_quota)} 點**(歐洲、亞洲各 30%,"
        f"其他洲每國上限 {OTHER_CAP})",
        f"配額均等值:歐洲 {base['歐洲']} 點/國,亞洲 {base['亞洲']} 點/國,"
        f"其他洲 {base['其他洲']} 點/國(點池不足者全給)",
        "",
    ]
    for cont in CONTINENT_DIRS:
        ccs = [cc for cc in pools if continents[cc] == cont]
        cont_quota = sum(quotas[cc] for cc in ccs)
        lines += [
            f"## {cont}({len(ccs)} 國,配額 {fmt(cont_quota)} 點,"
            f"佔 {cont_quota / total_quota * 100:.1f}%)",
            "",
            "| 代碼 | 國家 | 城市 | 點池 | 配額 | 佔全部 | 佔本洲 |",
            "|---|---|---|---|---|---|---|",
        ]
        for cc in sorted(ccs, key=lambda c: (-quotas[c], c)):
            q = quotas[cc]
            name = COUNTRY_NAMES.get(cc, cc)
            city = CITY_NAMES.get(cc, "")
            lines.append(
                f"| {cc} | {name} | {city} | {fmt(len(pools[cc]))} | {fmt(q)} "
                f"| {q / total_quota * 100:.2f}% "
                f"| {q / cont_quota * 100:.1f}% |"
            )
        lines.append("")
    (MAP_DIR / "point-counts.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    today = date.today().isoformat()

    continents = load_continents()
    pools = load_pools()
    missing = set(pools) - set(continents)
    if missing:
        sys.exit(f"錯誤:找不到洲別歸屬的點池 {sorted(missing)}")

    group_of = {
        cc: cont if cont in ("歐洲", "亞洲") else "其他洲"
        for cc, cont in continents.items()
    }

    # 先算其他洲(有上限),再反推歐亞預算維持 30%
    other_sizes = {cc: len(pool) for cc, pool in pools.items()
                   if group_of[cc] == "其他洲"}
    other_quotas = water_fill(999_999, other_sizes, max_per_country=OTHER_CAP)
    other_total = sum(other_quotas.values())
    # 其他洲 = 40%, 歐亞各 30% → 歐亞預算 = other_total * 0.3 / 0.4
    other_ratio = 1.0 - EUROPE_RATIO - ASIA_RATIO
    europe_budget = round(other_total * EUROPE_RATIO / other_ratio)
    asia_budget = round(other_total * ASIA_RATIO / other_ratio)
    total_budget = europe_budget + asia_budget + other_total

    quotas = dict(other_quotas)
    for group, budget in [("歐洲", europe_budget), ("亞洲", asia_budget)]:
        sizes = {cc: len(pool) for cc, pool in pools.items() if group_of[cc] == group}
        quotas.update(water_fill(budget, sizes))

    final_dir = MAP_DIR / "final"
    final_dir.mkdir(exist_ok=True)
    merged = []
    for cc in sorted(pools):
        chosen = select_locations(cc, pools[cc], quotas[cc])
        stem = CC_FILE.get(cc, cc.lower())
        (final_dir / f"{stem}.json").write_text(
            json.dumps(chosen, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        merged.extend(chosen)

    (MAP_DIR / f"{MAP_NAME}.json").write_text(
        json.dumps({"name": MAP_NAME, "customCoordinates": merged},
                   ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    write_point_counts(pools, quotas, continents, group_of, total_budget, today)

    print(f"配額 {fmt(len(merged))} 點(其他洲上限 {OTHER_CAP})")
    for group in ("歐洲", "亞洲", "其他洲"):
        s = sum(q for cc, q in quotas.items() if group_of[cc] == group)
        n = sum(1 for cc in quotas if group_of[cc] == group)
        print(f"  {group}: {fmt(s)} ({n} 國, {s / len(merged) * 100:.1f}%)")


if __name__ == "__main__":
    main()
