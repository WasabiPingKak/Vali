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

## 共通篩選條件

所有都會地圖使用 `Roads0 gte 3`（三叉路口以上），搭配 GeoJSON 多邊形框選範圍。
