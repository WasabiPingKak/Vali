#!/bin/bash
# 逐國跑 Vali 產生點位。自動跳過 locations/ 已有結果的國家。
# 用法:在 repo 根目錄執行 bash "maps/World's Biggest Cities 各國最大城市/run-all.sh"
set -e

MAP_DIR="maps/World's Biggest Cities 各國最大城市"
cd "$(dirname "$0")/../.."

mkdir -p "${MAP_DIR}/locations"

run_country() {
  local config_file="$1"
  local cc_file=$(basename "$config_file" .json)
  local output_file="${MAP_DIR}/locations/${cc_file}.json"

  if [ -f "$output_file" ]; then
    echo "SKIP $cc_file"
    return
  fi

  echo "--- Running $cc_file ---"
  "src/Vali/bin/Release/net8.0/Vali.exe" generate --file "$config_file" 2>&1 | grep -E "locations saved|Exception|OutOfMemory" || echo "  WARN: $cc_file no output match"

  local vali_output="${MAP_DIR}/config/${cc_file}-locations.json"
  if [ -f "$vali_output" ]; then
    mv "$vali_output" "$output_file"
  fi
  rm -f "${MAP_DIR}/config/${cc_file}-subdivision-distribution.txt"
}

for config in "${MAP_DIR}/config/"*.json; do
  run_country "$config"
done

echo ""
echo "=== 完成 ==="
echo "國家數:"
ls -1 "${MAP_DIR}/locations" 2>/dev/null | wc -l

echo ""
echo "各國點位數:"
for f in "${MAP_DIR}/locations/"*.json; do
  cc=$(basename "$f" .json)
  count=$(python -c "import json; d=json.load(open(r'$f',encoding='utf-8')); print(len(d.get('customCoordinates',d.get('locations',[]))))" 2>/dev/null || echo "?")
  echo "  $cc: $count"
done
