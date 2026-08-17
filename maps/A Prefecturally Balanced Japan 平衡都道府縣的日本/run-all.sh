#!/bin/bash
# 逐縣跑 Vali 產生日本各都道府縣點池。自動跳過 locations/ 已有結果的縣。
# 用法:在 repo 根目錄執行 bash "maps/A Prefecturally Balanced Japan 平衡都道府縣的日本/run-all.sh"
# 跑之前記得先 build:dotnet build src/Vali -c Release -p:TargetFrameworks=net8.0
set -e

MAP_DIR="maps/A Prefecturally Balanced Japan 平衡都道府縣的日本"
cd "$(dirname "$0")/../.."

mkdir -p "${MAP_DIR}/config" "${MAP_DIR}/locations"

for i in $(seq -w 1 47); do
  code="JP-${i}"
  lc="jp-${i}"
  config_file="${MAP_DIR}/config/${lc}.json"
  output_file="${MAP_DIR}/locations/${lc}.json"

  if [ -f "$output_file" ]; then
    echo "SKIP $code"
    continue
  fi

  if [ ! -f "$config_file" ]; then
    cat > "$config_file" <<EOFCFG
{
  "countryCodes": ["JP"],
  "subdivisionInclusions": { "JP": ["${code}"] },
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
