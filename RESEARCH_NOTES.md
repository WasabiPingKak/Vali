# Vali 研究筆記

> 調查日期：2026-06-06
> 目的：評估 Vali 對 GeoPingKak（Casual GeoGuessr）專案的可用性

---

## Vali 是什麼

.NET CLI 工具，從預先採集的 1 億+ Street View 地點資料庫中，依使用者定義的 JSON 配方（MapDefinition）篩選、分佈、輸出地點集合。產出的 JSON 可直接匯入 map-making.app 或 GeoGuessr。

安裝：`dotnet tool install -g vali`（需要 .NET 8 SDK）

## 資料來源與採集方式

資料採集 pipeline **不在這個 repo 裡**，是作者（slashp）另外維護的。這個 repo 只負責下載和使用已處理好的資料。

每個地點包含三種來源的資料：

| 來源 | 提供的資訊 | 說明 |
|---|---|---|
| **Google 內部 API** | 年份、月份、panoId、heading、解析度、海拔、是否 trekker | 逆向工程 `maps.googleapis.com` 的 gRPC-web 端點，不需 API key，不是付費 API |
| **OpenStreetMap** | 建築物數量、道路數量、路面材質、海岸/河流/鐵路距離、道路類型 | 預先從 OSM 查好，存進 protobuf |
| **Nominatim** | 國家碼、行政區碼（ISO 3166-2）、縣市名 | 反向地理編碼 |

地點基礎 = OSM 道路節點（node），所以彎道、路口、建築物附近的點密度較高，直線路段較少。

## 資料下載

```bash
vali download              # 互動式選擇國家下載
vali download --country TW # 下載台灣資料
```

- 來源：Cloudflare R2（`vali-download.slashp.workers.dev`）
- 格式：BZip2 壓縮的 protobuf `.bin` 檔
- 儲存位置：`C:\ProgramData\Vali\{CountryCode}\`
- 支援增量更新

## 可用指令一覽

| 指令 | 功能 |
|---|---|
| `vali generate --file map.json` | 依 JSON 配方產出地點集合 |
| `vali create-file` | 產生範本 JSON |
| `vali download` | 下載/更新各國資料 |
| `vali subdivisions --country "TW"` | 查看台灣行政區代碼與預設分佈 |
| `vali countries "TW"` | 查看國家級分佈資料 |
| `vali report --country "TW" --prop "County"` | 匯出台灣的縣市名統計 |
| `vali report --country "TW" --prop "Year"` | 匯出台灣的覆蓋年份統計 |
| `vali distribute-from-file` | 對外部地點檔案套用分佈演算法 |

## 台灣支援的行政區（ISO 3166-2）

共 20 個，對應到縣市層級：

```
TW-TPE 台北市    TW-NWT 新北市    TW-TAO 桃園市    TW-TXG 台中市
TW-TNN 台南市    TW-KHH 高雄市    TW-KEE 基隆市    TW-HSQ 新竹縣
TW-MIA 苗栗縣    TW-CHA 彰化縣    TW-NAN 南投縣    TW-YUN 雲林縣
TW-CYQ 嘉義縣    TW-PIF 屏東縣    TW-ILA 宜蘭縣    TW-HUA 花蓮縣
TW-TTT 台東縣    TW-PEN 澎湖縣    TW-KIN 金門縣    TW-LIE 連江縣（馬祖）
```

新竹市、嘉義市可能併入對應的縣處理。`County` 屬性可能有更細的鄉鎮區資訊（需下載資料後用 `vali report` 確認）。

## 篩選能力（跟 GeoPingKak 相關的）

### 可用的篩選屬性

```
# Google 來源
Year, Month, Lat, Lng, Heading, DrivingDirectionAngle, ArrowCount,
Elevation, DescriptionLength, IsScout

# OSM 來源
Surface, Buildings10/25/100/200, Roads0/10/25/50/100/200,
Tunnels10/200, IsResidential, ClosestCoast, ClosestLake,
ClosestRiver, ClosestRailway, HighwayType, WayId

# Nominatim 來源
CountryCode, SubdivisionCode, County
```

### 篩選層級

三層：全域 → 國家 → 行政區，每層可獨立設定。

### 篩選類型

1. **表達式篩選**：`Year >= 2020 and Buildings100 gte 4`
2. **偏好篩選**：「30% 未鋪裝路面 + 其餘任意」
3. **鄰近篩選**：指定參考點 CSV/JSON，取半徑內的地點
4. **GeoJSON 幾何篩選**：多邊形 include/exclude，可用 geojson.io 畫
5. **鄰居篩選**：根據周圍地點特徵篩選（例如「山頂」= 周圍所有點海拔都比自己低）

### Pano 驗證與選擇

產出地點時可呼叫 Google 內部 API 驗證每個地點是否有效，並選擇特定年份的街景：

- `Newest` / `Oldest` / `SecondNewest` / `SecondOldest`
- `Random` / `RandomNotNewest` / `RandomAvoidNewest` 等
- `YearMonthPeriod`：指定年月區間（精度到月）

## 產出格式

JSON，結構與 GeoGuessr / map-making.app 相容：

```json
{
  "customCoordinates": [
    {
      "lat": 25.033,
      "lng": 121.565,
      "panoId": "...",
      "heading": 90.5,
      "pitch": 0,
      "zoom": 0,
      "countryCode": "TW",
      "extra": { "tags": ["Year:2023", "Season:Summer"] }
    }
  ]
}
```

這個格式跟 GeoPingKak 的 `customCoordinates` 輸入格式完全一致，產出後可直接當 seed 地圖上傳。

---

## 對 GeoPingKak 專案的具體用途

### 確定能用

1. **產出 seed 地圖**（Phase 1 需要 5-10 張）

   範例配方 — 台北市區：
   ```json
   {
     "countryCodes": ["TW"],
     "distributionStrategy": {
       "key": "FixedCountByMaxMinDistance",
       "locationCountGoal": 500,
       "minMinDistance": 100
     },
     "subdivisionInclusions": { "TW": ["TW-TPE"] },
     "globalLocationFilter": "Buildings100 gte 4 and Year gte 2018",
     "output": { "panoVerificationStrategy": "Newest" }
   }
   ```

   範例配方 — 台灣鄉村：
   ```json
   {
     "countryCodes": ["TW"],
     "distributionStrategy": {
       "key": "FixedCountByMaxMinDistance",
       "locationCountGoal": 1000,
       "minMinDistance": 500
     },
     "globalLocationFilter": "Buildings200 eq 0 and Roads200 eq 1"
   }
   ```

   範例配方 — 台灣海岸線：
   ```json
   {
     "countryCodes": ["TW"],
     "distributionStrategy": {
       "key": "FixedCountByMaxMinDistance",
       "locationCountGoal": 800,
       "minMinDistance": 200
     },
     "globalLocationFilter": "ClosestCoast lt 100"
   }
   ```

   範例配方 — 用 GeoJSON 框特定區域（例如政大校園周邊）：
   ```json
   {
     "countryCodes": ["TW"],
     "distributionStrategy": {
       "key": "MaxCountByFixedMinDistance",
       "FixedMinDistance": 50
     },
     "geometryFilters": [{
       "filePath": "nccu-campus.geojson"
     }],
     "output": { "panoVerificationStrategy": "Newest" }
   }
   ```

2. **驗證地點存活** — 開 panoVerificationStrategy 可過濾掉 dead pano，減少玩家遇到黑畫面的機率

3. **探索資料品質** — 用 `vali report` 了解台灣各地的覆蓋密度、年份分佈，決定哪些地區適合做地圖

### 確定不適合

1. **不能整合進 web app** — .NET CLI + 15GB protobuf 資料，跑不動在 Cloud Run / Vercel 上
2. **不能做互動式框選** — 批次處理工具，不支援即時 UI 互動
3. **不能取代地圖編輯器** — 沒有視覺化介面，純 JSON 配方
4. **後期的「圈區域自動生成」功能不能直接用 Vali** — 但可以參考 Vali 的做法（OSM 節點 + Google 內部 API 驗證），自己寫輕量版

### 值得參考的程式碼

| 檔案 | 可參考什麼 |
|---|---|
| `src/Vali.Core/Google/GoogleApi.cs` | 逆向工程 Google Street View 內部 API 的呼叫方式、pano 驗證邏輯 |
| `src/Vali.Core/Google/GoogleApi.cs:86` | `SingleImageSearch` 端點：用 lat/lng 查 pano 資訊 |
| `src/Vali.Core/Google/GoogleApi.cs:337` | `GetMetadata` 端點：用 panoId 查 metadata |
| `src/Vali.Core/Google/GoogleApi.cs:503` | `Shorten`：產生 Google Maps 短網址 |
| `src/Vali.Core/LocationDistributor.cs` | 地點分佈演算法（binary search 最佳最小間距） |
| `src/Vali.Core/Hasher.cs` | Geohash 編解碼，空間查詢用 |

---

## 使用步驟（產 seed 地圖）

```bash
# 1. 安裝
dotnet tool install -g vali

# 2. 下載台灣資料（首次需要，可能幾百 MB）
vali download --country TW

# 3. 查看行政區分佈
vali subdivisions --country "TW"

# 4. 查看覆蓋年份統計
vali report --country "TW" --prop "Year"

# 5. 寫好 JSON 配方（見上方範例）
# 6. 產出地點
vali generate --file taipei-urban.json

# 7. 產出的 JSON 直接可當 GeoPingKak 的 seed 地圖上傳
```
