# A Starter World 入門的世界：工作交接

## 地圖目標

低難度世界市區圖，113 個國家/地區，每國只框 1~7 個主要城市（用 geojson 多邊形）。目標是讓初學者在熟悉的城市環境中練習辨識國家。

## 目前狀態（2026-08-04）

**110 國已全部產出點位**(含 2026-08 補收錄的 AL 阿爾巴尼亞)，結果在 `locations/{cc}.json`（檔名用 geojson 命名，英國是 `uk.json`）。各國 Vali 設定在 `config/{cc}.json`，各國點數統計見 `point-counts.md`。

**2026-08-04 點池已用新 filter 全面重產**（路口/河鐵交會版，見下方 Filter 條件摘要），並用 `allocate.py` 重跑分配，`final/` 與匯入檔都是新結果。SZ 同時換了重畫的城市框（原檔誤存為 Untitled.geojson）。**巴爾幹 pano 驗證已被本次分配覆蓋，尚未重驗**。

**分配腳本:`allocate.py`**（2026-08-04 重寫,舊腳本從未 commit 已失傳）。規則:總量 40,000 點、以國家為單位盡可能均分、歐洲與亞洲各上限 30%（water-filling,點池不足全給、配額回流）、新景（2020+）優先舊景補位、手選檔（dict 格式）自動合併並以 panoId 去重。一併重產 `point-counts.md` 與 `final-map-countries.md`。手選點國別歸屬走 Nominatim reverse geocode,快取在 `handpick-countries.json`（可手動修正,如聖誕島 AU→CX）,平常跑 `python allocate.py` 全離線,手選檔有新點時加 `--geocode`。抽選用固定 seed,同輸入重跑結果相同。

最終匯入檔:`A Starter World 入門的世界.json` = 40,000 自動配額點 + 89 手選點 = **40,089 點**,絕大多數鎖定官方 panoId。

手選檔:`locations/` 下所有 **GeoGuessr dict 格式**(`{name, customCoordinates}`)的檔案都會被分配腳本視為手選來源自動合併;裸陣列格式則是各國點池。目前有三個:

- `starter_world_handpick.json`(38 點):全球知名地標(雪梨歌劇院、自由女神、泰姬瑪哈、聖家堂等)+ EG 吉薩、CX 聖誕島、BR 巴西利亞
- `starter_world_bm.json`(30 點):百慕達漢米爾頓(Vali 資料庫整島只有 113 點,程式產不出結果,改手選)
- `beginner_world_bt_hanpick_extend.json`(21 點):不丹手動補點(新 filter 後 BT 點池只剩 62,重複率太高,2026-08 手選補強)

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
  "globalLocationFilter": "Roads0 gt 2 or ArrowCount gte 3 or ClosestRiver lt 100 or ClosestRailway lt 100",
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

## Pano 驗證(Newest,2026-08 對巴爾幹執行過)

資料湖收錄有時差(Google 已上線的新景,湖裡可能只有舊 pano)。對 final 點跑 Newest 驗證可繞過資料湖:逐點呼叫 Google API,鎖定現場最新的**官方** pano(版權字串 `© YYYY Google` 過濾,非官方照片球自動排除、自動遞補次新官方)。2026-08 對巴爾幹 9 國跑過一輪,RS/ME/AL 的新景比例從 40/12/7% 升到 89/87/67%。

**注意**:驗證結果寫在 `final/{cc}.json`。重跑分配腳本會從點池重產 final 並覆蓋驗證結果,之後要再驗一次。合併匯入檔若只需重組(不重抽),用 merge-only 流程直接串 final + 手選檔。

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

1. **`globalLocationFilter`**:`Roads0 gt 2 or ArrowCount gte 3 or ClosestRiver lt 100 or ClosestRailway lt 100`
   - `Roads0 gt 2`:該點有 3 條以上道路交會 = 交叉路口(OSM 路網資料)
   - `ArrowCount gte 3`:街景有 3 個以上導航箭頭 = Google 端的路口訊號,補 OSM 路口標註不全的國家(JP 等)
   - `ClosestRiver lt 100` / `ClosestRailway lt 100`:距河流/鐵路 100m 內 = 道路與河川鐵道的交會處
   - 2026-08 第二次改版:舊條件 `Buildings200 gte 3 and ArrowCount gte 2` 會選到大量筆直路段中間的點,難以定位,社群做法是放路口/河鐵交會等有定位線索的位置。`Buildings200` 移除:geojson 城市框已保證市區感,此條件在框內近乎恆真
   - 已知代價:OSM 與 Google 訊號都稀疏的小國點池大縮,歷史上 `Roads0 gte 2` 曾因此在前一版被整個移除過,本次為了點位品質接受縮減,點池過小的國家個案處理(放寬或手選)
2. **`enableDefaultLocationFilters: true`** 啟用的預設 filter:
   - 排隧道（`Tunnels10 == 0`）
   - 排壞圖（無 description 且非 Scout 的 coverage）
   - FI/EC/NG 特殊畫質門檻（Gen4+）
3. **geometry filter**:geojson 多邊形限定範圍（union 模式）

## 技術備註

- Vali country code 用 ISO 3166-1 alpha-2,英國是 `GB`（不是 `UK`）,geojson 檔名是 `uk.geojson`
- locations JSON 可直接匯入 GeoGuessr map making（外面包一層 `{"name":"...", "customCoordinates": [...]}` 即可）
- 舊的 `MaxCountByFixedMinDistance` 逐國結果（`{cc}-locations.json`,無 `-evenly`）數字偏低,不要用
