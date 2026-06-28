# maps/

台灣 GeoGuessr 地圖資料，每張地圖一個資料夾。

## 目錄結構

```
maps/
└── {地圖名稱}/
    ├── *.geojson            框選範圍（在 geojson.io 繪製的多邊形）
    ├── {地圖名稱}.json      最終合併結果（匯入 map-making.app 用）
    ├── distribution.json    各行政區的落點數量統計
    ├── config/              Vali 設定檔（每個行政區分組一個）
    │   └── *.json
    └── output/              Vali 產出（中間產物，可重新產生）
        ├── *.json           各分組的落點 JSON
        └── *-subdivision-distribution.txt
```

## 檔案說明

| 檔案 | 用途 |
|---|---|
| `*.geojson` | 用 geojson.io 手動框選的都會區多邊形，作為 Vali 的 geometry filter |
| `{地圖名稱}.json` | 所有分組合併後的最終落點，格式相容 map-making.app / GeoGuessr |
| `config/*.json` | Vali 的 MapDefinition，定義篩選條件、密度、涵蓋的行政區 |
| `output/*.json` | Vali 單次執行的原始產出，合併後成為最終 JSON |
| `distribution.json` | 各行政區的落點數量（格式見下方） |
| `output/*-distribution.txt` | Vali 產出的原始分佈統計 |

## distribution.json 格式

供前端顯示每個行政區有多少個落點。如果你要上傳自己的地圖並使用這個功能，請在地圖資料夾內建立 `distribution.json`，遵照以下格式：

```json
{
  "totalLocations": 5730,
  "regions": [
    { "code": "TW-TPE", "count": 413 },
    { "code": "TW-NWT", "count": 727 }
  ]
}
```

| 欄位 | 類型 | 必填 | 說明 |
|---|---|---|---|
| `totalLocations` | number | 是 | 地圖內的落點總數 |
| `regions` | array | 是 | 各行政區的落點統計 |
| `regions[].code` | string | 是 | ISO 3166-2 行政區代碼（如 `TW-TPE`、`JP-13`、`US-CA`） |
| `regions[].count` | number | 是 | 該行政區的落點數量 |

注意事項：
- `code` 使用 [ISO 3166-2](https://en.wikipedia.org/wiki/ISO_3166-2) 標準代碼，與語言無關。行政區的顯示名稱由前端根據使用者語系決定。
- `regions` 內所有 `count` 的加總應等於 `totalLocations`。
- 排列順序不限，前端自行決定排序方式。

## 產生流程

1. 在 geojson.io 繪製多邊形，匯出為 `.geojson`
2. 撰寫 `config/*.json` 設定檔（指定行政區、密度、篩選條件）
3. 執行 `vali generate --file config/xxx.json`（從專案根目錄執行）
4. 合併所有 `output/*.json` 為最終 `{地圖名稱}.json`

## 現有地圖

| 地圖 | 說明 | 點數 |
|---|---|---|
| 台灣的都會 | 全台都會區聯集，大城市 400m、其餘 200m | 5,730 |
| 北部台灣的都會 | 北北基桃竹宜都會區 | 1,932 |
| 中部台灣的都會 | 苗栗/台中/彰化/南投/雲林/嘉義都會區 | 1,264 |
| 南部台灣的都會 | 台南/高雄/屏東/嘉義都會區 | 1,212 |
| 東部台灣的都會與全台離島 | 花蓮/台東/澎湖/金門/連江都會區 | 375 |
| 台灣聚落 | 全台灣聚落，按涵蓋密度分配，壓低六都比重 | 8,549 |

## 台灣聚落

全台灣範圍的聚落地圖，不限定都會區。

### 篩選條件

- `Buildings200 gte 4`：200m 內至少 4 棟建築
- `Roads0 gte 2`：至少兩條道路經過

### 分佈策略

使用 `FixedCountByCoverageDensity`，搭配 `treatCountriesAsSingleSubdivision` 將全台視為單一區域，純粹依據涵蓋密度的 geohash cluster 分配點數，不套用預設的行政區面積權重。

- 目標點數：10,000（實際 8,549，偏鄉合格點不足）
- 最小間距：150m
- `coverageDensityTuningFactor`：0.7（壓縮高密度區域配額）

### 與都會地圖的差異

| | 都會地圖 | 聚落地圖 |
|---|---|---|
| 範圍 | GeoJSON 多邊形框選的都會區 | 全台灣，無框選 |
| 門檻 | `Roads0 gte 3` | `Buildings200 gte 4 and Roads0 gte 2` |
| 分佈 | 按行政區面積權重 | 按涵蓋密度，跨行政區統一計算 |
| 目的 | 城市路口辨識 | 涵蓋各級聚落（城鎮到村莊） |

## 都會地圖共通篩選條件

所有都會地圖使用 `Roads0 gte 3`，搭配 GeoJSON 多邊形框選範圍。

## 聚落地圖共通參數

所有聚落地圖共用以下設定，新建聚落地圖時以此為基準：

| 參數 | 值 | 說明 |
|---|---|---|
| `globalLocationFilter` | `Buildings200 gte 4 and Roads0 gte 2` | 200m 內至少 4 棟建築且至少 2 條道路 |
| `distributionStrategy.key` | `FixedCountByCoverageDensity` | 依涵蓋密度分配固定數量 |
| `distributionStrategy.minMinDistance` | `150` | 最小間距 150m |
| `distributionStrategy.coverageDensityTuningFactor` | `0.7` | 壓縮高密度區域配額 |
| `output.locationTags` | `["Buildings200", "Roads0", "SubdivisionCode"]` | 標準輸出標籤 |

各地圖依國家調整的參數：`locationCountGoal`、`subdivisionDistribution`、`treatCountriesAsSingleSubdivision`。
