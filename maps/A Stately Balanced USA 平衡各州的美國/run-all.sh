#!/bin/bash
# 逐州跑 Vali 產生美國各州點池。自動跳過 locations/ 已有結果的州。
# 用法:在 repo 根目錄執行 bash "maps/A Stately Balanced USA 平衡各州的美國/run-all.sh"
# 跑之前記得先 build:dotnet build src/Vali -c Release -p:TargetFrameworks=net8.0
set -e

MAP_DIR="maps/A Stately Balanced USA 平衡各州的美國"
cd "$(dirname "$0")/../.."

mkdir -p "${MAP_DIR}/config" "${MAP_DIR}/locations"

# 50 州 + 華盛頓特區;波多黎各、關島等領地在 Vali 是獨立國家代碼,不在這張圖
STATES="AK AL AR AZ CA CO CT DC DE FL GA HI IA ID IL IN KS KY LA MA MD ME MI MN MO MS MT NC ND NE NH NJ NM NV NY OH OK OR PA RI SC SD TN TX UT VA VT WA WI WV WY"

for st in $STATES; do
  code="US-${st}"
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
  "countryCodes": ["US"],
  "subdivisionInclusions": { "US": ["${code}"] },
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

  echo "--- Running $code ($(date +%H:%M:%S)) ---"
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
