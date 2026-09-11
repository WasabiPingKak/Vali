#!/bin/bash
# 逐州跑 Vali 產生澳洲各州/領地點池。自動跳過 locations/ 已有結果的州。
# 用法:在 repo 根目錄執行 bash "maps/A Stately Balanced Australia 平衡各州的澳洲/run-all.sh"
# 跑之前記得先 build:dotnet build src/Vali -c Release -p:TargetFrameworks=net8.0
set -e

MAP_DIR="maps/A Stately Balanced Australia 平衡各州的澳洲"
cd "$(dirname "$0")/../.."

mkdir -p "${MAP_DIR}/config" "${MAP_DIR}/locations"

# 6 州 + 2 領地;Jervis Bay Territory 資料只有 4.6KB,另外用「JBT」代碼跑一次看看有幾點
STATES="ACT NSW NT QLD SA TAS VIC WA"

for st in $STATES; do
  code="AU-${st}"
  lc=$(echo "$st" | tr 'A-Z' 'a-z')
  config_file="${MAP_DIR}/config/${lc}.json"
  output_file="${MAP_DIR}/locations/${lc}.json"

  if [ -f "$output_file" ]; then
    echo "SKIP $code"
    continue
  fi

  if [ ! -f "$config_file" ]; then
    cat > "$config_file" <<EOFCFG
{
  "countryCodes": ["AU"],
  "subdivisionInclusions": { "AU": ["${code}"] },
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

# Jervis Bay Territory:Vali 內部的 subdivision 名稱不是 ISO 代碼,直接用全名
jbt_config="${MAP_DIR}/config/jbt.json"
jbt_output="${MAP_DIR}/locations/jbt.json"
if [ ! -f "$jbt_output" ]; then
  if [ ! -f "$jbt_config" ]; then
    cat > "$jbt_config" <<'EOFCFG'
{
  "countryCodes": ["AU"],
  "subdivisionInclusions": { "AU": ["Jervis Bay Territory"] },
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
  echo "--- Running Jervis Bay Territory ---"
  "src/Vali/bin/Release/net8.0/Vali.exe" generate --file "$jbt_config" 2>&1 | grep -E "locations saved|Exception|OutOfMemory" || echo "  WARN: JBT no output match"
  if [ -f "${MAP_DIR}/config/jbt-locations.json" ]; then
    mv "${MAP_DIR}/config/jbt-locations.json" "$jbt_output"
  fi
  rm -f "${MAP_DIR}/config/jbt-subdivision-distribution.txt"
fi

echo ""
echo "=== 完成 ==="
ls -1 "${MAP_DIR}/locations" | wc -l
