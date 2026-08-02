#!/bin/bash
# 逐國跑 Vali 產生點位。自動跳過 locations/ 已有結果的國家。
# 用法:在 repo 根目錄執行 bash "maps/A Starter World 入門的世界/run-all.sh"
set -e

MAP_DIR="maps/A Starter World 入門的世界"
cd "$(dirname "$0")/../.."

run_country() {
  local geojson_path="$1"
  local continent=$(basename "$(dirname "$geojson_path")")
  local cc_file=$(basename "$geojson_path" .geojson)

  # country code:大寫,uk 檔名對應 GB
  local cc
  if [ "$cc_file" = "uk" ]; then cc="GB"; else cc=$(echo "$cc_file" | tr 'a-z' 'A-Z'); fi

  local config_file="${MAP_DIR}/config/${cc_file}.json"
  local output_file="${MAP_DIR}/locations/${cc_file}.json"

  if [ -f "$output_file" ]; then
    echo "SKIP $cc"
    return
  fi

  if [ ! -f "$config_file" ]; then
    cat > "$config_file" <<EOFCFG
{
  "countryCodes": ["${cc}"],
  "distributionStrategy": {
    "key": "EvenlyByDistanceWithinCountry",
    "fixedMinDistance": 100
  },
  "globalLocationFilter": "Buildings200 gte 3 and Roads0 gte 2",
  "enableDefaultLocationFilters": true,
  "geometryFilters": [
    { "filePath": "${MAP_DIR}/${continent}/${cc_file}.geojson", "inclusionMode": "include", "combinationMode": "union" }
  ],
  "output": {
    "locationTags": ["CountryCode"],
    "panoIdCountryCodes": ["*"]
  }
}
EOFCFG
  fi

  echo "--- Running $cc ($continent) ---"
  dotnet run --project src/Vali -c Release -f net8.0 -p:TargetFrameworks=net8.0 -- generate --file "$config_file" 2>&1 | grep -E "locations saved|Exception|OutOfMemory" || echo "  WARN: $cc no output match"

  # Vali 輸出在 config 旁邊,搬到 locations/ 並清掉副產品
  local vali_output="${MAP_DIR}/config/${cc_file}-locations.json"
  if [ -f "$vali_output" ]; then
    mv "$vali_output" "$output_file"
  fi
  rm -f "${MAP_DIR}/config/${cc_file}-subdivision-distribution.txt"
}

find "$MAP_DIR" -name "*.geojson" | sort | while read -r geojson; do
  run_country "$geojson"
done

echo ""
echo "=== 完成 ==="
ls -1 "${MAP_DIR}/locations" | wc -l
