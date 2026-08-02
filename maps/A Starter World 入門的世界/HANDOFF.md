# A Starter World 入門的世界：工作交接

## 地圖目標

低難度世界市區圖，113 個國家/地區，每國只框 1~7 個主要城市（用 geojson 多邊形）。目標是讓初學者在熟悉的城市環境中練習辨識國家。

## 目前狀態（2026-08-04）

**110 國已全部產出點位**(含 2026-08 補收錄的 AL 阿爾巴尼亞)，結果在 `locations/{cc}.json`（檔名用 geojson 命名，英國是 `uk.json`）。各國 Vali 設定在 `config/{cc}.json`，各國點數統計見 `point-counts.md`。

最終匯入檔:`A Starter World 入門的世界.json` = 40,000 自動配額點 + 68 手選點 = **40,068 點**,絕大多數鎖定官方 panoId。

手選檔:`locations/` 下所有 **GeoGuessr dict 格式**(`{name, customCoordinates}`)的檔案都會被分配腳本視為手選來源自動合併;裸陣列格式則是各國點池。目前有兩個:

- `starter_world_handpick.json`(38 點):全球知名地標(雪梨歌劇院、自由女神、泰姬瑪哈、聖家堂等)+ EG 吉薩、CX 聖誕島、BR 巴西利亞
- `starter_world_bm.json`(30 點):百慕達漢米爾頓(Vali 資料庫整島只有 113 點,程式產不出結果,改手選)

合併規則:手選點接在自動點後面,panoId 重複的自動去除。

手選對應的背景:

- **EG**（埃及）、**CX**（聖誕島）：countries.md 原本就標註手選
- **BM**（百慕達）：資料庫覆蓋不足
- **BR 的巴西利亞**：城市層級手選，其餘巴西城市照跑

已移除的國家：

- **MP**（北馬里亞納群島）：2026-08 決定不收錄

## 最終採用的策略

`EvenlyByDistanceWithinCountry` + `fixedMinDistance: 100`：

```json
{
  "countryCodes": ["XX"],
  "distributionStrategy": {
    "key": "EvenlyByDistanceWithinCountry",
    "fixedMinDistance": 100
  },
  "globalLocationFilter": "Buildings200 gte 3",
  "enableDefaultLocationFilters": true,
  "geometryFilters": [
    { "filePath": "maps/A Starter World 入門的世界/洲名/xx.geojson", "inclusionMode": "include", "combinationMode": "union" }
  ],
  "output": { "locationTags": ["CountryCode", "Year"], "panoIdCountryCodes": ["*"] }
}
```

output 兩個設定的用途:

- `panoIdCountryCodes: ["*"]`:每點鎖定官方 panoId,避免 GeoGuessr 遊玩時就近解析到非官方照片球
- `locationTags` 加 `Year`:點位帶年份標籤,分配腳本據此做「新景(2020+)優先、舊景補位」的抽選——新舊 coverage 並存的國家(如巴爾幹)會優先抽新景;新景不足配額的(RS、ME)新景全收後用舊景補滿

選擇原因：

1. 不分行政區,goal 不會被 geojson 沒覆蓋到的空行政區分走（`MaxCountByFixedMinDistance` 的核心問題,詳見 git history 裡的舊版 HANDOFF）
2. 不用設 goal count,固定 100m 間距自動塞滿多邊形
3. 多邊形跨行政區也不會漏點（geometry filter 在每個行政區獨立套用）

## 已修復:大檔 OOM（commit `64a9968`,已 merge develop）

`EvenlyByDistanceInCountry` 原本把整個行政區 bin 檔一次反序列化進記憶體再過濾,大檔（GB-ENG 842MB、BR-SP 490MB 等）直接 OOM。已改成 protobuf-net `DeserializeItems` 串流分塊（5 萬筆一塊）邊讀邊過濾,記憶體用量只跟過濾後留下的點數成正比。GB/BR/MX/ID/US 全部通過。

注意:有設 neighbor filter 的地圖仍走整檔讀取路徑（鄰居查詢需要整個行政區的點）,這張圖沒用到所以不受影響。

## 各國點數

完整清單與配額見 `point-counts.md`(每次重跑分配後自動重產)。點數差異來自多邊形面積與當地 Street View 覆蓋密度,微型國點少是正常現象。

## 批次腳本

`run-all.sh`:逐國跑、自動跳過 `locations/` 已有結果的國家。腳本邏輯:掃描各洲目錄的 geojson → 產生單國 config（`config/{cc}.json`,已存在則沿用）→ `vali generate` → 結果搬到 `locations/{cc}.json`。重跑某國:刪掉 `locations/{cc}.json` 再執行腳本。檔名 `uk.geojson` 對應 country code `GB`。

多國一起跑（一個 config 塞整洲）會 OOM,務必逐國跑。

## Filter 條件摘要

1. **`globalLocationFilter`**:`Buildings200 gte 3`(200m 內至少 3 棟建築)
   - 原本另有 `Roads0 gte 2`(限定路口),2026-08 移除:OSM 路網稀疏的國家(BT 等)會被誤殺,放寬後小國點池明顯變大
2. **`enableDefaultLocationFilters: true`** 啟用的預設 filter:
   - 排隧道（`Tunnels10 == 0`）
   - 排壞圖（無 description 且非 Scout 的 coverage）
   - FI/EC/NG 特殊畫質門檻（Gen4+）
3. **geometry filter**:geojson 多邊形限定範圍（union 模式）

## 技術備註

- Vali country code 用 ISO 3166-1 alpha-2,英國是 `GB`（不是 `UK`）,geojson 檔名是 `uk.geojson`
- locations JSON 可直接匯入 GeoGuessr map making（外面包一層 `{"name":"...", "customCoordinates": [...]}` 即可）
- 舊的 `MaxCountByFixedMinDistance` 逐國結果（`{cc}-locations.json`,無 `-evenly`）數字偏低,不要用
