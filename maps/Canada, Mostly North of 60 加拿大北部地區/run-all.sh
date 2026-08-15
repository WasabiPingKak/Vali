#!/bin/bash
# 逐區跑 Vali 產生各省/地區點池。自動跳過 locations/ 已有結果的省份。
# 目前 locations/ 內容是從「A Provincially Balanced Canada 平衡省份的加拿大」
# 複製過來的,想重產請先刪掉對應檔案。
# 用法:在 repo 根目錄執行 bash "maps/Canada, Mostly North of 60 加拿大北部地區/run-all.sh"
# 跑之前記得先 build:dotnet build src/Vali -c Release -p:TargetFrameworks=net8.0
set -e

MAP_DIR="maps/Canada, Mostly North of 60 加拿大北部地區"
cd "$(dirname "$0")/../.."

REGIONS="YT NT NU AB BC MB NB NL NS ON PE QC SK"

for terr in $REGIONS; do
  lc=$(echo "$terr" | tr 'A-Z' 'a-z')
  config_file="${MAP_DIR}/config/${lc}.json"
  output_file="${MAP_DIR}/locations/${lc}.json"

  if [ -f "$output_file" ]; then
    echo "SKIP $terr"
    continue
  fi

  if [ ! -f "$config_file" ]; then
    cat > "$config_file" <<EOFCFG
{
  "countryCodes": ["CA"],
  "subdivisionInclusions": { "CA": ["CA-${terr}"] },
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

  echo "--- Running CA-$terr ---"
  "src/Vali/bin/Release/net8.0/Vali.exe" generate --file "$config_file" 2>&1 | grep -E "locations saved|Exception|OutOfMemory" || echo "  WARN: $terr no output match"

  vali_output="${MAP_DIR}/config/${lc}-locations.json"
  if [ -f "$vali_output" ]; then
    mv "$vali_output" "$output_file"
  fi
  rm -f "${MAP_DIR}/config/${lc}-subdivision-distribution.txt"
done

echo ""
echo "=== 完成 ==="
ls -1 "${MAP_DIR}/locations" | wc -l
