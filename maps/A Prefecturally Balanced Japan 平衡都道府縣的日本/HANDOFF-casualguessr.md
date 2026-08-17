# HANDOFF:CasualGuessr 匯入時自動計算行政區分佈

給在 `D:\Github_Local_Workspace\CasualGuessr` 開新 session 用的交接文件。
撰寫日期:2026-08-17(Vali 專案 session 交接)。

## 一句話目標

地圖匯入時,行政區分佈(`maps.region_distribution`)改由前端**自動計算**,
不再需要另外手動上傳 distribution.json。逐國支援:先做日本,未來做到哪個
國家再加哪個國家,不用一次全做。

## 背景

- Vali 端產了新地圖 `A Prefecturally Balanced Japan 平衡都道府縣的日本`
  (94,000 點,47 都道府縣各 2,000,tags 帶 `JP-XX` 縣代碼)。
- 過去的流程:Vali 端 allocate.py 另外產 `distribution.json`
  (`{regions:[{code,count}]}`),上傳到編輯頁的行政區欄位,PATCH 進
  `maps.region_distribution`。作者(使用者)不想再做這個手動步驟。
- 日本圖已**不再產 distribution.json**,等這個功能上線後直接匯入即可。

## CasualGuessr 現況(本次已讀過的程式碼)

- **匯入流程**:`frontend/src/app/maps/[slug]/edit/page.tsx` 的 `importFile`
  (約 197~305 行):parseMapJson → 分批 upsert `locations` →
  `detectCountryPoints`(country-coder 判國,回傳**各國點座標分組**)→
  `finish_map_import` RPC 寫入 country_codes / country_counts
- **行政區手動上傳**:同檔 `importRegionFile`(約 116~147 行):
  讀 JSON → 驗證 `{regions:[{code,count}]}` → PATCH `region_distribution`
- **`parseMapJson`**(`frontend/src/lib/map-import.ts`):只保留
  lat/lng/heading/pitch/zoom/panoId/panoDate,**`extra.tags` 會被丟掉**,
  DB 的 locations 表也沒有 tags 欄位。所以 Vali 埋的 `JP-XX` tag
  進不了資料庫,**不要走 tag 方案**,除非願意動 schema
- **顯示端已就緒**:`frontend/src/lib/region-names.ts` 已有 JP-01~47
  (與 TW 各縣市)的中文名;`CountryDistribution.tsx` 已會渲染
  regionDistribution。**顯示端不用改**

## 建議做法(細節由實作 session 定案)

跟判國同一個模式:座標 point-in-polygon,行政區邊界資料逐國提供。

1. 新增 `frontend/src/lib/region-detect.ts`:
   - 支援國家登記表:`{ JP: "/boundaries/jp-adm1.json" }`,做到哪國加哪國
   - `detectRegionCounts(points, countryCode)`:載入該國 admin-1 邊界,
     逐點 point-in-polygon(每個多邊形先用 bbox 預篩,再做 ray casting),
     回傳 `{regions:[{code,count}]}`,code 用 ISO 3166-2(`JP-01`)
     以對上 region-names.ts
2. 邊界資料放 `frontend/public/boundaries/`,**匯入時才 fetch**,
   不進遊戲 bundle。目標單國 < 1MB(簡化版即可,顯示用統計不需高精度)
   - 建議來源:geoBoundaries gbOpen JPN ADM1 的 simplified 版
     (API:`https://www.geoboundaries.org/api/current/gbOpen/JPN/ADM1/`
     的 `simplifiedGeometryGeoJSON`)。**注意:要驗證 shapeISO 欄位
     是否為 `JP-01` 格式**,不是的話要做一層代碼對應
   - 備選:Natural Earth admin-1(有 iso_3166_2 屬性,本身就是簡化版)
   - GADM 站台(geodata.ucdavis.edu)2026-08-17 連不上,別依賴它
3. 插入點:`importFile` 裡 `detectCountryPoints` 之後(約 270 行)。
   `pointsByCountry` 已經把各國點分好組,取主國家(點數最多者)判斷
   是否在支援清單,是就把**該國的點**丟進 detectRegionCounts,
   結果 PATCH `region_distribution`(重用 importRegionFile 的 PATCH 路徑)
4. 容錯原則(沿用上次離群國家事件的教訓):
   - 簡化邊界在縣界會有少量誤差,但誤差只影響「算進哪個縣」,
     純顯示用途,可接受,**不要做逐點驗證、不要擋匯入**
   - 落在所有縣多邊形外的點(海岸簡化縫隙)直接不計入分佈即可,
     或歸給最近的 bbox,擇一,別讓它 throw
   - 自動計算失敗(邊界檔載不到等)時靜默略過,保留手動上傳路徑當後備
5. 手動上傳功能**保留**:不支援的國家(還沒做的、多國圖)仍走手動
6. 未支援國家的地圖匯入行為完全不變

## 驗證素材

- 匯入 `D:\Github_Local_Workspace\Vali\maps\A Prefecturally Balanced Japan
  平衡都道府縣的日本\A Prefecturally Balanced Japan 平衡都道府縣的日本.json`
  (94,000 點),期望 region_distribution 為 47 縣、每縣接近 2,000
  (簡化邊界在縣界的零星誤差可接受,總和應為 94,000 或略少)
- 每點的 `extra.tags` 第三個元素是 Vali 端用高精度資料算好的縣代碼
  (`JP-01`~`JP-47`),可拿來當比對基準寫測試(tag 不進 DB,但測試
  可以直接讀地圖 JSON 檔比對偵測結果)
- 台灣現有地圖若之後想改用自動計算,region-names.ts 的 TW 代碼是
  `TW-TPE` 這種字母碼,邊界資料的代碼對應要另外確認

## UI 文案提醒

遵守全域規則:日常用語,禁止技術術語(schema、endpoint 等),
禁止「——」「;」與「不是…而是…」句型。例:進度文字用
「正在整理各地區的題目數量...」這類說法。

## 流程提醒

CasualGuessr 是程式碼修改,依全域規則:確認 `develop` 乾淨 →
`EnterWorktree` 開 feature branch → 在 worktree 內改 → 完成後回主 repo 操作。
