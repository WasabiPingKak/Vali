#!/bin/bash
# 逐縣市跑 Vali 產生台灣各縣市點池。自動跳過 locations/ 已有結果的縣市。
# 用法:在 repo 根目錄執行 bash "maps/A County-Balanced Taiwan 平衡縣市的台灣/run-all.sh"
# 跑之前記得先 build:dotnet build src/Vali -c Release -p:TargetFrameworks=net8.0
set -e

MAP_DIR="maps/A County-Balanced Taiwan 平衡縣市的台灣"
cd "$(dirname "$0")/../.."

mkdir -p "${MAP_DIR}/config" "${MAP_DIR}/locations"

COUNTIES="CHA CYI CYQ HSQ HSZ HUA ILA KEE KHH KIN LIE MIA NAN NWT PEN PIF TAO TNN TPE TTT TXG YUN"

# 點池湊不到配額的小縣市改用 50m 間距。實測基隆在 100m 下,最近鄰距離有
# 兩成貼著 100m 下限,老市區街廓只隔 50~80m 的路口被迫二選一;放寬到 50m
# 點數幾乎翻倍。其餘縣市點池早就超過配額,維持 100m。
DENSE_COUNTIES="KEE PEN KIN LIE"

for c in $COUNTIES; do
  code="TW-${c}"
  lc=$(echo "$c" | tr 'A-Z' 'a-z')
  config_file="${MAP_DIR}/config/${lc}.json"
  output_file="${MAP_DIR}/locations/${lc}.json"

  min_distance=100
  case " $DENSE_COUNTIES " in *" $c "*) min_distance=50 ;; esac

  if [ -f "$output_file" ]; then
    echo "SKIP $code"
    continue
  fi

  if [ ! -f "$config_file" ]; then
    cat > "$config_file" <<EOFCFG
{
  "countryCodes": ["TW"],
  "subdivisionInclusions": { "TW": ["${code}"] },
  "distributionStrategy": {
    "key": "EvenlyByDistanceWithinCountry",
    "fixedMinDistance": ${min_distance}
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
