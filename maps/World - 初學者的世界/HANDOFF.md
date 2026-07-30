# World - 初學者的世界：工作交接

## 地圖目標

低難度世界市區圖，113 個國家/地區，每國只框 1~7 個主要城市（用 geojson 多邊形）。目標是讓初學者在熟悉的城市環境中練習辨識國家。

## 目前狀態（2026-07-31）

**109 國已全部產出點位**，結果在 `config/_tmp/{cc}-evenly-locations.json`。

尚缺：

- **HR**（克羅埃西亞）：geojson 還沒畫
- **EG**（埃及）、**CX**（聖誕島）：countries.md 標註為「手選，不用程式跑」

## 最終採用的策略

`EvenlyByDistanceWithinCountry` + `fixedMinDistance: 100`：

```json
{
  "countryCodes": ["XX"],
  "distributionStrategy": {
    "key": "EvenlyByDistanceWithinCountry",
    "fixedMinDistance": 100
  },
  "globalLocationFilter": "Buildings200 gte 3 and Roads0 gte 2",
  "enableDefaultLocationFilters": true,
  "geometryFilters": [
    { "filePath": "maps/World - 初學者的世界/洲名/xx.geojson", "inclusionMode": "include", "combinationMode": "union" }
  ],
  "output": { "locationTags": ["CountryCode"] }
}
```

選擇原因：

1. 不分行政區,goal 不會被 geojson 沒覆蓋到的空行政區分走（`MaxCountByFixedMinDistance` 的核心問題,詳見 git history 裡的舊版 HANDOFF）
2. 不用設 goal count,固定 100m 間距自動塞滿多邊形
3. 多邊形跨行政區也不會漏點（geometry filter 在每個行政區獨立套用）

## 已修復:大檔 OOM（commit `64a9968`,已 merge develop）

`EvenlyByDistanceInCountry` 原本把整個行政區 bin 檔一次反序列化進記憶體再過濾,大檔（GB-ENG 842MB、BR-SP 490MB 等）直接 OOM。已改成 protobuf-net `DeserializeItems` 串流分塊（5 萬筆一塊）邊讀邊過濾,記憶體用量只跟過濾後留下的點數成正比。GB/BR/MX/ID/US 全部通過。

注意:有設 neighbor filter 的地圖仍走整檔讀取路徑（鄰居查詢需要整個行政區的點）,這張圖沒用到所以不受影響。

## 各國點數（前幾名）

TW 15,997 / JP 11,997 / SG 10,331 / CA 8,933 / KR 8,059 / ID 7,380 / TR 7,348 / MY 7,192 / CZ 6,332 / KZ 5,943 / BG 5,841 / GB 5,750 / ES 5,438 / IN 5,319 / HK 5,308 / US 5,061 / DE 5,030 / AE 5,035 / NL 4,870 …

完整清單直接看 `config/_tmp/` 目錄。點數差異來自多邊形面積與當地 Street View 覆蓋密度,微型國（MC 38、ST 25、BM 4）是正常現象。

## 批次腳本

逐國跑、自動跳過已完成的國家。腳本邏輯:掃描各洲目錄的 geojson → 產生單國 config（`config/_tmp/{cc}-evenly.json`）→ `vali generate` → 輸出 `{cc}-evenly-locations.json`。檔名 `uk.geojson` 對應 country code `GB`。

多國一起跑（一個 config 塞整洲）會 OOM,務必逐國跑。

## Filter 條件摘要

1. **`globalLocationFilter`**:`Buildings200 gte 3 and Roads0 gte 2`
   - 200m 內至少 3 棟建築 + 至少在 2 條路交會處
2. **`enableDefaultLocationFilters: true`** 啟用的預設 filter:
   - 排隧道（`Tunnels10 == 0`）
   - 排壞圖（無 description 且非 Scout 的 coverage）
   - FI/EC/NG 特殊畫質門檻（Gen4+）
3. **geometry filter**:geojson 多邊形限定範圍（union 模式）

## 技術備註

- Vali country code 用 ISO 3166-1 alpha-2,英國是 `GB`（不是 `UK`）,geojson 檔名是 `uk.geojson`
- locations JSON 可直接匯入 GeoGuessr map making（外面包一層 `{"name":"...", "customCoordinates": [...]}` 即可）
- 舊的 `MaxCountByFixedMinDistance` 逐國結果（`{cc}-locations.json`,無 `-evenly`）數字偏低,不要用
