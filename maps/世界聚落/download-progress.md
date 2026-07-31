# 世界鄉村地圖 — 資料下載進度

## 已完成（8）— 共 14 GB

- [x] TW — Taiwan (305 MB)
- [x] US — United States of America (5.2 GB)
- [x] RU — Russia (454 MB)
- [x] BR — Brazil (3.0 GB)
- [x] CA — Canada (1.1 GB)
- [x] AU — Australia (920 MB)
- [x] ID — Indonesia (1.9 GB)
- [x] MX — Mexico (1.1 GB)

## 待下載（119）— 暫停中（磁碟空間不足）

依權重由大到小排列，方便優先處理高權重國家。

### 權重 ≥ 2000（5 國，大型覆蓋）
- [ ] AR — Argentina (2700)
- [ ] ZA — South Africa (2696)
- [ ] JP — Japan (2651)
- [ ] IN — India (2342)
- [ ] TH — Thailand (2300)

### 權重 1000–1999（24 國，中大型覆蓋，含原 ≥2000 剩餘）

- [ ] FR — France (2136)
- [ ] CO — Colombia (2117)
- [ ] PH — Philippines (2061)
- [ ] ES — Spain (2055)
- [ ] DE — Germany (2028)
- [ ] MY — Malaysia (2000)
- [ ] TR — Turkey (1929)
- [ ] NG — Nigeria (1880)
- [ ] IT — Italy (1843)
- [ ] SE — Sweden (1816)
- [ ] CL — Chile (1801)
- [ ] PE — Peru (1750)
- [ ] GB — United Kingdom (1711)
- [ ] VN — Vietnam (1600)
- [ ] KE — Kenya (1600)
- [ ] NO — Norway (1510)
- [ ] PL — Poland (1500)
- [ ] NZ — New Zealand (1500)
- [ ] RO — Romania (1400)
- [ ] UA — Ukraine (1300)
- [ ] GR — Greece (1240)
- [ ] FI — Finland (1230)
- [ ] SN — Senegal (1204)
- [ ] EC — Ecuador (1200)

### 權重 500–999（28 國，中型覆蓋）

- [ ] BO — Bolivia (1100)
- [ ] PY — Paraguay (1100)
- [ ] KH — Cambodia (1080)
- [ ] AT — Austria (1000)
- [ ] GT — Guatemala (950)
- [ ] LK — Sri Lanka (905)
- [ ] GE — Georgia (904)
- [ ] IE — Ireland (904)
- [ ] BG — Bulgaria (900)
- [ ] CZ — Czechia (900)
- [ ] DK — Denmark (900)
- [ ] HU — Hungary (900)
- [ ] KR — South Korea (900)
- [ ] UY — Uruguay (900)
- [ ] BD — Bangladesh (802)
- [ ] NL — Netherlands (801)
- [ ] PT — Portugal (800)
- [ ] NA — Namibia (750)
- [ ] HR — Croatia (750)
- [ ] KZ — Kazakhstan (706)
- [ ] CH — Switzerland (700)
- [ ] BA — Bosnia and Herzegovina (690)
- [ ] BE — Belgium (655)
- [ ] OM — Oman (625)
- [ ] IL — Israel (620)
- [ ] KG — Kyrgyzstan (601)
- [ ] EE — Estonia (600)
- [ ] IS — Iceland (600)
- [ ] LT — Lithuania (600)
- [ ] LV — Latvia (600)
- [ ] RS — Serbia (600)
- [ ] SK — Slovakia (600)
- [ ] BW — Botswana (600)
- [ ] CR — Costa Rica (600)
- [ ] PA — Panama (600)
- [ ] JO — Jordan (600)
- [ ] AE — United Arab Emirates (600)
- [ ] NP — Nepal (550)
- [ ] TN — Tunisia (500)

### 權重 100–499（23 國，小型覆蓋）

- [ ] MN — Mongolia (442)
- [ ] SI — Slovenia (440)
- [ ] BT — Bhutan (400)
- [ ] AL — Albania (400)
- [ ] SZ — Eswatini (380)
- [ ] LS — Lesotho (300)
- [ ] LU — Luxembourg (300)
- [ ] ME — Montenegro (300)
- [ ] DO — Dominican Republic (250)
- [ ] LA — Laos (250)
- [ ] MK — North Macedonia (250)
- [ ] PS — State of Palestine (250)
- [ ] QA — Qatar (250)
- [ ] UG — Uganda (250)
- [ ] MT — Malta (230)
- [ ] RW — Rwanda (208)
- [ ] HK — Hong Kong (200)
- [ ] SG — Singapore (200)
- [ ] FO — Faroe Islands (200)
- [ ] PR — Puerto Rico (180)
- [ ] AD — Andorra (150)
- [ ] GL — Greenland (150)
- [ ] SM — San Marino (150)
- [ ] VI — U.S. Virgin Islands (150)
- [ ] CW — Curaçao (130)
- [ ] RE — Réunion (125)
- [ ] AX — Åland Islands (120)
- [ ] CY — Cyprus (120)
- [ ] MO — Macao (110)
- [ ] GU — Guam (100)
- [ ] IM — Isle of Man (100)
- [ ] MP — Northern Mariana Islands (100)

### 權重 < 100（7 國，極小覆蓋）

- [ ] AS — American Samoa (80)
- [ ] JE — Jersey (80)
- [ ] GI — Gibraltar (50)
- [ ] LI — Liechtenstein (50)
- [ ] BM — Bermuda (50)
- [ ] MC — Monaco (50)
- [ ] ST — Sao Tome and Principe (50)
- [ ] PK — Pakistan (34)
- [ ] MG — Madagascar (31)
- [ ] CC — Cocos (Keeling) Islands (30)
- [ ] CX — Christmas Island (30)
- [ ] UM — United States Minor Outlying Islands (15)
- [ ] BY — Belarus (13)
- [ ] EG — Egypt (10)
- [ ] PN — Pitcairn (10)
- [ ] LB — Lebanon (38)
- [ ] MQ — Martinique (5)
- [ ] ML — Mali (5)

## 下載指令

```bash
dotnet run --project src/Vali -- download --country {國碼}
```

## 測試結果

- 2026-06-22：US + TW 測試生成 4,989 點成功，filter `Buildings200 gte 5 and Roads25 gte 3` 效果合理
