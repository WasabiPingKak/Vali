# 世界鄉村地圖 — 官方街景國家清單

來源：`Weights.OfficialWorld`（`src/Vali.Core/Weights.cs`）
總計：**127 國/地區**

## 篩選條件

- 200 公尺內至少 5 棟建物（`Buildings200 gte 5`）
- 25 公尺內至少 3 段路段，即交叉路口（`Roads25 gte 3`）
- 不限街景年份
- 不排除特定道路類型
- 目標 100,000 個點位
- 分佈策略：`FixedCountByCoverageDensity`

## 國家清單（按洲別）

### 歐洲（40）

| 國碼 | 國家 | 權重 |
|---|---|---|
| AD | Andorra | 150 |
| AL | Albania | 400 |
| AT | Austria | 1000 |
| AX | Åland Islands | 120 |
| BA | Bosnia and Herzegovina | 690 |
| BE | Belgium | 655 |
| BG | Bulgaria | 900 |
| BY | Belarus | 13 |
| CH | Switzerland | 700 |
| CY | Cyprus | 120 |
| CZ | Czechia | 900 |
| DE | Germany | 2028 |
| DK | Denmark | 900 |
| EE | Estonia | 600 |
| ES | Spain | 2055 |
| FI | Finland | 1230 |
| FO | Faroe Islands | 200 |
| FR | France | 2136 |
| GB | United Kingdom | 1711 |
| GI | Gibraltar | 50 |
| GR | Greece | 1240 |
| HR | Croatia | 750 |
| HU | Hungary | 900 |
| IE | Ireland | 904 |
| IM | Isle of Man | 100 |
| IS | Iceland | 600 |
| IT | Italy | 1843 |
| JE | Jersey | 80 |
| LI | Liechtenstein | 50 |
| LT | Lithuania | 600 |
| LU | Luxembourg | 300 |
| LV | Latvia | 600 |
| MC | Monaco | 50 |
| ME | Montenegro | 300 |
| MK | North Macedonia | 250 |
| NL | Netherlands | 801 |
| NO | Norway | 1510 |
| PL | Poland | 1500 |
| PT | Portugal | 800 |
| RO | Romania | 1400 |
| RS | Serbia | 600 |
| SE | Sweden | 1816 |
| SI | Slovenia | 440 |
| SK | Slovakia | 600 |
| SM | San Marino | 150 |

### 亞洲（25）

| 國碼 | 國家 | 權重 |
|---|---|---|
| AE | United Arab Emirates | 600 |
| BD | Bangladesh | 802 |
| BT | Bhutan | 400 |
| GE | Georgia | 904 |
| HK | Hong Kong | 200 |
| ID | Indonesia | 3030 |
| IL | Israel | 620 |
| IN | India | 2342 |
| JO | Jordan | 600 |
| JP | Japan | 2651 |
| KG | Kyrgyzstan | 601 |
| KH | Cambodia | 1080 |
| KR | South Korea | 900 |
| KZ | Kazakhstan | 706 |
| LA | Laos | 250 |
| LB | Lebanon | 38 |
| LK | Sri Lanka | 905 |
| MN | Mongolia | 442 |
| MO | Macao | 110 |
| MY | Malaysia | 2000 |
| NP | Nepal | 550 |
| OM | Oman | 625 |
| PH | Philippines | 2061 |
| PK | Pakistan | 34 |
| PS | State of Palestine | 250 |
| QA | Qatar | 250 |
| SG | Singapore | 200 |
| TH | Thailand | 2300 |
| TR | Turkey | 1929 |
| TW | Taiwan | 906 |
| VN | Vietnam | 1600 |

### 非洲（13）

| 國碼 | 國家 | 權重 |
|---|---|---|
| BW | Botswana | 600 |
| EG | Egypt | 10 |
| GH | Ghana | 1250 |
| KE | Kenya | 1600 |
| LS | Lesotho | 300 |
| MG | Madagascar | 31 |
| ML | Mali | 5 |
| NA | Namibia | 750 |
| NG | Nigeria | 1880 |
| RW | Rwanda | 208 |
| SN | Senegal | 1204 |
| SZ | Eswatini | 380 |
| TN | Tunisia | 500 |
| UG | Uganda | 250 |
| ZA | South Africa | 2696 |

### 北美洲（11）

| 國碼 | 國家 | 權重 |
|---|---|---|
| AS | American Samoa | 80 |
| BM | Bermuda | 50 |
| CA | Canada | 3566 |
| CR | Costa Rica | 600 |
| CW | Curaçao | 130 |
| DO | Dominican Republic | 250 |
| GT | Guatemala | 950 |
| GU | Guam | 100 |
| MP | Northern Mariana Islands | 100 |
| MQ | Martinique | 5 |
| MX | Mexico | 2900 |
| PA | Panama | 600 |
| PR | Puerto Rico | 180 |
| US | United States of America | 4945 |
| VI | U.S. Virgin Islands | 150 |

### 南美洲（8）

| 國碼 | 國家 | 權重 |
|---|---|---|
| AR | Argentina | 2700 |
| BO | Bolivia | 1100 |
| BR | Brazil | 3836 |
| CL | Chile | 1801 |
| CO | Colombia | 2117 |
| EC | Ecuador | 1200 |
| PE | Peru | 1750 |
| PY | Paraguay | 1100 |
| UY | Uruguay | 900 |

### 大洋洲（3）

| 國碼 | 國家 | 權重 |
|---|---|---|
| AU | Australia | 3200 |
| NZ | New Zealand | 1500 |
| CC | Cocos (Keeling) Islands | 30 |
| CX | Christmas Island | 30 |
| PN | Pitcairn | 10 |

### 其他（遠洋屬地）

| 國碼 | 國家 | 權重 |
|---|---|---|
| GL | Greenland | 150 |
| RE | Réunion | 125 |
| ST | Sao Tome and Principe | 50 |
| UM | United States Minor Outlying Islands | 15 |

### 東歐/中亞

| 國碼 | 國家 | 權重 |
|---|---|---|
| RU | Russia | 4314 |
| UA | Ukraine | 1300 |

## 備註

- 權重數字來自 `Weights.OfficialWorld`，代表該國在地圖中的相對分佈比例
- 低權重國家（EG=10, ML=5, MQ=5, BY=13 等）覆蓋極有限，產出點位可能很少
- 喬治亞（GE, 權重 904）已確認在清單中，2026 年 6 月新上線的街景需先更新資料湖
