#!/bin/bash
# 逐區跑 Vali 產生紐西蘭各大區點池。自動跳過 locations/ 已有結果的區。
# 用法:在 repo 根目錄執行 bash "maps/A Regionally Balanced New Zealand 平衡大區的紐西蘭/run-all.sh"
# 跑之前記得先 build:dotnet build src/Vali -c Release -p:TargetFrameworks=net8.0
set -e

MAP_DIR="maps/A Regionally Balanced New Zealand 平衡大區的紐西蘭"
cd "$(dirname "$0")/../.."

mkdir -p "${MAP_DIR}/config" "${MAP_DIR}/locations"

# 16 個大區(ISO 3166-2:NZ);查塔姆群島領地 Vali 資料沒有獨立 subdivision,不跑
REGIONS="AUK BOP CAN GIS HKB MBH MWT NSN NTL OTA STL TAS TKI WGN WKO WTC"

for rg in $REGIONS; do
  code="NZ-${rg}"
  lc=$(echo "$rg" | tr 'A-Z' 'a-z')
  config_file="${MAP_DIR}/config/${lc}.json"
  output_file="${MAP_DIR}/locations/${lc}.json"

  if [ -f "$output_file" ]; then
    echo "SKIP $code"
    continue
  fi

  if [ ! -f "$config_file" ]; then
    cat > "$config_file" <<EOFCFG
{
  "countryCodes": ["NZ"],
  "subdivisionInclusions": { "NZ": ["${code}"] },
  "distributionStrategy": {
    "key": "EvenlyByDistanceWithinCountry",
    "fixedMinDistance": 100
  },
  "globalLocationFilter": "Roads0 gt 2 or ArrowCount gte 3 or ClosestRiver lt 100 or ClosestRailway lt 100",
  "enableDefaultLocationFilters": true,
  "output": {
    "locationTags": ["CountryCode", "Year"],
    "panoIdCountryCodes": ["*"]
  }
}
EOFCFG
  fi

  echo "--- Running $code ---"
  "src/Vali/bin/Release/net8.0/Vali.exe" generate --file "$config_file" 2>&1 | grep -E "locations saved|Exception|OutOfMemory" || echo "  WARN: $code no output match"

  vali_output="${MAP_DIR}/config/${lc}-locations.json"
  if [ -f "$vali_output" ]; then
    mv "$vali_output" "$output_file"
  fi
  rm -f "${MAP_DIR}/config/${lc}-subdivision-distribution.txt"
done

echo ""
echo "=== 完成 ==="
ls -1 "${MAP_DIR}/locations" | wc -l
