# HANDOFF:CasualGuessr 匯入容錯改進

給在 `D:\Github_Local_Workspace\CasualGuessr` 開新 session 用的交接文件。
撰寫日期:2026-08-08(Vali 專案 session 交接)。

## 一句話目標

CasualGuessr 匯入地圖時,國家判定結果出現「離群國家」(例:五萬點的加拿大圖被判出 11 點美國)
不應該讓作者卡住或造成資料髒污,要改成**寬容處理**(警告 + 讓作者選擇怎麼辦),
而不是追求更精準的邊界資料。

## 事件背景(發生了什麼)

1. Vali 這邊產了一張加拿大地圖 `A Provincially Balanced Canada 平衡省份的加拿大`
   (49,623 點,9 省各 5,000 + PE/YT/NT/NU 全收,tags 帶省代碼)。
2. 上傳到 CasualGuessr 後,有 28 個點被判成美國,無法歸屬省份。
3. Vali 端用 GADM 高精度邊界清掉「真的在美國境內或貼線 250m 內」的點後重新上傳,
   仍剩 11 個點被判美國。
4. 追根因:CasualGuessr 前端用 `@rapideditor/country-coder` 判國,它的邊界資料是
   刻意簡化的(全世界 600KB),河界路段與真實國界差距可達數公里。那 11 個點
   實際都在加拿大側(NB 聖約翰河沿岸的跨加公路 10 個 + QC 邊界村 Pohénégamook 1 個),
   但落在 country-coder 簡化後的美國多邊形內。
5. Vali 端把 country-coder 的 `borders.json` 複製過來,產圖時直接用**前端同一份資料**
   預先過濾,本地重現 11 個點誤差為零,重產後三道檢查歸零。此圖的問題已解決。

## 為什麼 CasualGuessr 還需要改

- Vali 的資料端過濾只保護「這條 pipeline 產的圖」。未來匯入任何其他來源的地圖
  (別人做的、手選的、舊圖),同樣的邊境誤判還是會出現。
- 方向**不是**換更精準的邊界資料:country-coder 的體積/速度就是為瀏覽器設計的,
  換高精度資料前端載不動,而且任兩套邊界資料在河界本來就不會完全一致,
  追求前端判斷完美是打不贏的仗。要改的是**錯誤處理**。

## CasualGuessr 現況(本次已讀過的程式碼)

- **判國邏輯**:`frontend/src/lib/country-detect.ts`
  - `detectCountryCode(lat, lng)`:country-coder `featuresContaining`,
    取 territory/country 層級的 iso1A2
  - `detectCountryCounts(locations)`:逐點判國統計數量
- **匯入流程**:`frontend/src/app/maps/[slug]/edit/page.tsx`(約 200~284 行)
  - 瀏覽器直打 Supabase 分批 upsert `locations`(不經 Worker,避免免費方案 CPU 超限)
  - 全部上傳後跑 `detectCountryCounts` → `finish_map_import` RPC 寫入
    `maps.country_codes` 與 `maps.country_counts`
  - **注意:匯入本身不會 hard-fail**,離群國家是寫進 country_counts 之後
    在地圖頁的國家分佈列表現形(例:出現「美國 11 點」但省份分佈裡對不上)
- **行政區分佈**:同檔約 110~136 行,distribution.json(`{regions:[{code,count}]}`)
  另外上傳,PATCH 到 `maps.region_distribution`,純顯示用 metadata,無逐點驗證
- **顯示**:`frontend/src/components/map/CountryDistribution.tsx`
  吃 countryCodes/countryCounts + regionDistribution
- **其他吃判國結果的地方**(改動時要留意,不一定要動):
  - `frontend/src/app/play/[slug]/page.tsx:262`:玩家猜測座標的判國
  - `frontend/src/lib/award-engine.ts:57`:每回合落點判國 → visit 貼紙。
    邊境誤判點理論上會發錯國家的貼紙,但 Vali 產的圖已在資料端清乾淨,
    此風險只存在於其他來源的地圖

## 建議的改動方向(細節由實作 session 定案)

匯入偵測完 `countryCounts` 後,加一層離群偵測與作者選擇:

1. **離群判定**:某國點數佔比極低(例如 < 0.5% 且存在一個佔比壓倒性的主國家)
   時視為疑似邊境誤判。門檻自己斟酌,別做成硬規則卡正常的多國圖
   (世界圖、雙國圖的少數國家是正常的)。
2. **給作者選擇,不要擋**:警告顯示離群國家與點數(能列出座標更好),
   讓作者選「這些點歸入主國家」或「維持偵測結果」。單國圖 + 幾個離群點的
   場景下,歸入主國家幾乎永遠是對的。
3. UI 文案遵守全域規則:日常用語,不出現技術術語。

## 驗證素材:當初被誤判的 11 個點

新版地圖已剔除這些點。要測試離群偵測邏輯,可拿舊版地圖檔重現,
或直接用這 11 個座標做單元測試(country-coder 會判它們為 US,實際全在加拿大):

| 省 | lat | lng | panoId |
|---|---|---|---|
| NB | 47.16479 | -67.92732 | dLsBKeoJrMoixQdRgXUD1g |
| NB | 45.18113 | -67.29497 | DLHnm5r7IM5B-bIt1duvYw |
| NB | 47.35681 | -68.36393 | 24xE0XnV4sprNo84uSutqw |
| NB | 47.28636 | -68.43024 | HAWsFORCqBrfgFqV0z8b3w |
| NB | 47.16691 | -67.93062 | 1ca6hp4jgZR2Jx6M9gtiRQ |
| NB | 47.35541 | -68.36709 | 7Bb0mGaOAMIPbdSmegAneA |
| NB | 47.28631 | -68.43293 | 3ZOVkM9gbgthcBt2B-9-IA |
| NB | 47.28636 | -68.43629 | kOwCQ2L92ZHK5sDxyLiIlg |
| NB | 45.17344 | -67.29670 | -oj0YJQ_0a1nJcK4BmojIA |
| NB | 47.16101 | -67.92605 | fVOBQgkhF1Kf04oebvKwGw |
| QC | 47.45752 | -69.20290 | rr9BHYPzaXUDA7235lKKKQ |

## 流程提醒

CasualGuessr 是程式碼修改,依全域規則:確認 `develop` 乾淨 → `EnterWorktree`
開 feature branch → 在 worktree 內改 → 完成後回主 repo 操作。
