#!/bin/bash
# 逐區跑 Vali 產生香港 18 區點池。自動跳過 locations/ 已有結果的區。
# 用法:在 repo 根目錄執行 bash "maps/A District-Balanced Hong Kong 平衡行政區的香港/run-all.sh"
# 跑之前記得先 build:dotnet build src/Vali -c Release -p:TargetFrameworks=net8.0
set -e

MAP_DIR="maps/A District-Balanced Hong Kong 平衡行政區的香港"
cd "$(dirname "$0")/../.."

mkdir -p "${MAP_DIR}/config" "${MAP_DIR}/locations"

# HK 18 區 HASC_2 對應的 slug (中西/東/離島/九龍城/葵青/觀塘/北/西貢/沙田/深水埗/南/大埔/荃灣/屯門/灣仔/黃大仙/油尖旺/元朗)
SLUGS=(cw ea is kc ki ku no sk st ss so tp tw tm wc wt yt yl)

for slug in "${SLUGS[@]}"; do
  config_file="${MAP_DIR}/config/hk-${slug}.json"
  output_file="${MAP_DIR}/locations/hk-${slug}.json"

  if [ -f "$output_file" ]; then
    echo "SKIP hk-${slug}"
    continue
  fi

  if [ ! -f "$config_file" ]; then
    echo "  MISSING config: $config_file"
    continue
  fi

  echo "--- Running hk-${slug} ---"
  "src/Vali/bin/Release/net8.0/Vali.exe" generate --file "$config_file" 2>&1 | grep -E "locations saved|Exception|OutOfMemory" || echo "  WARN: hk-${slug} no output match"

  vali_output="${MAP_DIR}/config/hk-${slug}-locations.json"
  if [ -f "$vali_output" ]; then
    mv "$vali_output" "$output_file"
  fi
  rm -f "${MAP_DIR}/config/hk-${slug}-subdivision-distribution.txt"
done

echo ""
echo "=== 完成 ==="
ls -1 "${MAP_DIR}/locations" | wc -l
