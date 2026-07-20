#!/usr/bin/env python3
"""
從地圖 JSON 產生 distribution.json（各行政區落點數量統計）。

用法:
    python scripts/gen-distribution.py maps/台灣人測試/台灣人測試.json
    python scripts/gen-distribution.py maps/台灣人測試/

需要 shapely: pip install shapely
邊界資料: scripts/gadm41_TWN_2.json (GADM Taiwan level-2, ~120KB)

目前只支援台灣座標。如需支援其他國家，下載對應的 GADM level-2 GeoJSON
放到 scripts/ 並擴充 BOUNDARY_FILES。
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

try:
    from shapely.geometry import Point, shape
except ImportError:
    print("需要 shapely: pip install shapely", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent

GADM_NAME_TO_ISO = {
    "Taipei": "TW-TPE",
    "NewTaipei": "TW-NWT",
    "Taoyuan": "TW-TAO",
    "Taichung": "TW-TXG",
    "Tainan": "TW-TNN",
    "Kaohsiung": "TW-KHH",
    "Keelung": "TW-KEE",
    "HsinchuCity": "TW-HSZ",
    "HsinchuCounty": "TW-HSQ",
    "ChiayiCity": "TW-CYI",
    "ChiayiCounty": "TW-CYQ",
    "Changhua": "TW-CHA",
    "Miaoli": "TW-MIA",
    "Nantou": "TW-NAN",
    "Yulin": "TW-YUN",
    "Pingtung": "TW-PIF",
    "Yilan": "TW-ILA",
    "Hualien": "TW-HUA",
    "Taitung": "TW-TTT",
    "Penghu": "TW-PEN",
    "Kinmen": "TW-KIN",
    "Lienkiang": "TW-LIE",
}

BOUNDARY_FILES = {
    "TW": SCRIPT_DIR / "gadm41_TWN_2.json",
}


def load_boundaries():
    regions = []
    for country, path in BOUNDARY_FILES.items():
        if not path.exists():
            print(f"找不到邊界資料: {path}", file=sys.stderr)
            print(
                "請執行: curl -sL https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_TWN_2.json"
                f" -o {path}",
                file=sys.stderr,
            )
            sys.exit(1)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for feature in data["features"]:
            name = feature["properties"]["NAME_2"]
            iso = GADM_NAME_TO_ISO.get(name)
            if iso and feature.get("geometry"):
                regions.append((iso, shape(feature["geometry"])))
    return regions


def classify_point(lat, lng, regions):
    pt = Point(lng, lat)
    for iso, polygon in regions:
        if polygon.contains(pt):
            return iso
    # 邊界附近的點可能落在多邊形外，用最近距離 fallback
    min_dist = float("inf")
    nearest = None
    for iso, polygon in regions:
        d = polygon.distance(pt)
        if d < min_dist:
            min_dist = d
            nearest = iso
    return nearest


def find_map_json(path):
    p = Path(path)
    if p.is_file() and p.suffix == ".json":
        return p
    if p.is_dir():
        for f in sorted(p.iterdir()):
            if f.suffix == ".json" and f.name != "distribution.json":
                try:
                    with open(f, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    if "customCoordinates" in data:
                        return f
                except (json.JSONDecodeError, KeyError):
                    continue
    return None


def main():
    parser = argparse.ArgumentParser(
        description="從地圖 JSON 產生 distribution.json"
    )
    parser.add_argument("path", help="地圖 JSON 檔案或資料夾路徑")
    args = parser.parse_args()

    map_json = find_map_json(args.path)
    if not map_json:
        print(
            f"找不到含 customCoordinates 的 JSON: {args.path}",
            file=sys.stderr,
        )
        sys.exit(1)

    dist_path = map_json.parent / "distribution.json"

    with open(map_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    coords = [(loc["lat"], loc["lng"]) for loc in data["customCoordinates"]]
    total = len(coords)
    print(f"{map_json.name}: {total} 個座標")

    print("載入邊界資料...")
    regions = load_boundaries()
    print(f"已載入 {len(regions)} 個行政區邊界")

    counter = Counter()
    unmapped = []

    for i, (lat, lng) in enumerate(coords):
        iso = classify_point(lat, lng, regions)
        if iso:
            counter[iso] += 1
        else:
            unmapped.append((i, lat, lng))

    result = [
        {"code": code, "count": count} for code, count in counter.most_common()
    ]
    output = {"regions": result}

    with open(dist_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    mapped = sum(counter.values())
    print(f"\n完成: {mapped} 已對應, {len(unmapped)} 未對應")

    if unmapped:
        print("未對應的座標:")
        for idx, lat, lng in unmapped:
            print(f"  [{idx}] ({lat:.6f}, {lng:.6f})")

    print(f"\n{dist_path}:")
    for r in result:
        print(f"  {r['code']}: {r['count']}")


if __name__ == "__main__":
    main()
