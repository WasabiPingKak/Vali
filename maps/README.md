# maps/

台灣 GeoGuessr 地圖資料，每張地圖一個資料夾。

## 目錄結構

```
maps/
└── {地圖名稱}/
    ├── *.geojson          框選範圍（在 geojson.io 繪製的多邊形）
    ├── {地圖名稱}.json    最終合併結果（匯入 map-making.app 用）
    ├── config/            Vali 設定檔（每個行政區分組一個）
    │   └── *.json
    └── output/            Vali 產出（中間產物，可重新產生）
        ├── *.json         各分組的落點 JSON
        └── *-subdivision-distribution.txt  行政區分佈統計
```

## 檔案說明

| 檔案 | 用途 |
|---|---|
| `*.geojson` | 用 geojson.io 手動框選的都會區多邊形，作為 Vali 的 geometry filter |
| `{地圖名稱}.json` | 所有分組合併後的最終落點，格式相容 map-making.app / GeoGuessr |
| `config/*.json` | Vali 的 MapDefinition，定義篩選條件、密度、涵蓋的行政區 |
| `output/*.json` | Vali 單次執行的原始產出，合併後成為最終 JSON |
| `output/*-distribution.txt` | Vali 產出的行政區分佈統計 |

## 產生流程

1. 在 geojson.io 繪製多邊形，匯出為 `.geojson`
2. 撰寫 `config/*.json` 設定檔（指定行政區、密度、篩選條件）
3. 執行 `vali generate --file config/xxx.json`（從專案根目錄執行）
4. 合併所有 `output/*.json` 為最終 `{地圖名稱}.json`

## 現有地圖

| 地圖 | 說明 | 點數 |
|---|---|---|
| 台灣都會 | 全台都會區聯集，大城市 400m、其餘 200m | 5,730 |
| 北台灣-都會 | 北北基桃竹宜都會區 | 1,932 |
| 中台灣-都會 | 苗栗/台中/彰化/南投/雲林/嘉義都會區 | 1,264 |
| 南台灣-都會 | 台南/高雄/屏東/嘉義都會區 | 1,212 |
| 東台灣、離島-都會 | 花蓮/台東/澎湖/金門/連江都會區 | 363 |

## 共通篩選條件

所有都會地圖使用 `Roads0 gte 3`（三叉路口以上），搭配 GeoJSON 多邊形框選範圍。
