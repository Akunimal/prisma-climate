# App glossary (T34)

Authoritative wording for every technical term the Flutter app shows in its 10
locales. Translations must follow this file; if a translation needs to change,
change it here first and then in the ARB files.

Locales: `en` (template), `es`, `pt`, `fr`, `de`, `it`, `ru`, `zh`, `ja`, `hi`.

## Core terms

| Concept | en (source) | es | pt | fr | de | it | ru | zh | ja | hi |
|---|---|---|---|---|---|---|---|---|---|---|
| ensemble | ensemble | ensamble | ensemble | ensemble | Ensemble | ensemble | ансамбль | 集合 | アンサンブル | एन्सेम्बल |
| ensemble member | member | miembro | membro | membre | Mitglied | membro | член ансамбля | 集合成员 | メンバー | सदस्य |
| raw / uncalibrated | raw, uncalibrated | crudo, sin calibrar | bruto, não calibré | brut, non calibré | roh, unkalibriert | grezzo, non calibrato | сырой, некалиброванный | 原始、未校准 | 未校正 | कच्चा, बिना कैलिब्रेशन |
| lead day | lead day | día de anticipación | dia de antecedência | jour de prévision | Vorhersagetag | giorno di previsione | день прогноза | 预报时效 | 予報日数 | लीड दिवस |
| median | median | mediana | mediana | médiane | Median | mediana | медиана | 中位数 | 中央値 | माध्यिका |
| 10–90 % range | 10–90 % band | banda 10–90 % | faixa 10–90 % | bande 10–90 % | 10–90-%-Band | fascia 10–90 % | полоса 10–90 % | 10–90% 区间 | 10–90% 帯 | 10–90% श्रेणी |
| issue time | issue time | hora de emisión | hora de emissão | heure d'émission | Abgabezeitpunkt | ora di emissione | время выпуска | 起报时间 | 発表時刻 | जारी समय |
| verification | verification | verificación | verificação | vérification | Verifikation | verifica | верификация | 検验 | 検証 | सत्यापन |
| observation | observation | observación | observação | observation | Beobachtung | osservazione | наблюдение | 观测 | 観測 | अवलोकन |

Notes on deliberate choices:

- **"ensemble" stays untranslated** where that is the community norm: `pt`, `fr`,
  `it`. `es` uses *ensamble* (WMO/SMN usage), `de` capitalises *Ensemble* as a
  German noun, `ru`/`zh`/`ja`/`hi` use the established local terms.
- **"lead day"** is the axis concept `+N d`. `zh` uses *预报时效* (forecast lead
  time), the standard CMA term, not a literal calque; `hi` keeps the technical
  loanword *लीड दिवस* because IMD documents write lead time as *लीड टाइम*.
- **"raw / uncalibrated"** must never be softened. Every locale keeps both parts
  (raw *and* not calibrated), never only one.
- **`issue time`** is displayed converted to Argentina time (UTC−3) in every
  locale; only the label is translated, never the timezone.

## UI labels

| Concept | en (source) | es | pt | fr | de | it | ru | zh | ja | hi |
|---|---|---|---|---|---|---|---|---|---|---|
| Stations (tab) | Stations | Estaciones | Estações | Stations | Stationen | Stazioni | Станции | 观测站 | 観測所 | स्टेशन |
| Forecast (tab) | Forecast | Pronóstico | Previsão | Prévisions | Vorhersage | Previsioni | Прогноз | 预报 | 予報 | पूर्वानुमान |
| About / Status (tab) | About / Status | Acerca de / Estado | Sobre / Estado | À propos / État | Über / Status | Informazioni / Stato | О приложении / Статус | 关于 / 状态 | 情報 / 状態 | जानकारी / स्थिति |
| no data | no data | sin datos | sem dados | aucune donnée | keine Daten | nessun dato | нет данных | 无数据 | データなし | कोई डेटा नहीं |
| Retry | Retry | Reintentar | Tentar novamente | Réessayer | Erneut versuchen | Riprova | Повторить | 重试 | 再試行 | पुनः प्रयास |
| Loading data… | Loading data… | Cargando datos… | Carregando dados… | Chargement des données… | Daten werden geladen… | Caricamento dati… | Загрузка данных… | 正在加载数据… | データを読み込み中… | डेटा लोड हो रहा है… |
| Language | Language | Idioma | Idioma | Langue | Sprache | Lingua | Язык | 语言 | 言語 | भाषा |

## Units, ids and attribution (never translated)

These stay byte-identical in all 10 locales:

- Units: `°C`, `mm`, `UTC−3`.
- Model ids/labels: `ECMWF IFS`, `GFS`, `ecmwf_ifs025`, `gfs_seamless`.
- Dataset and document ids: `latest.json`, `about.json`, `stations/*.json`,
  `regtemp`, schema `1.0`.
- Licence names: `CC BY 2.5 AR`, `CC BY 4.0`, `Copernicus C3S`, etc.
- The attribution line **"Weather data by Open-Meteo.com"** verbatim, as
  required by the Open-Meteo attribution policy. A translated explanation may
  sit next to it, but the line itself is never localised.
- Station names (`La Quiaca`, `Buenos Aires`, …): proper names, not translated.
- `about.json`'s `status` keys (`forecasts`, `verification`, `observations`) and
  its English values are data; the app renders its own localised copy.

## Honesty invariants (must survive every translation)

1. Forecasts are **raw and uncalibrated** — no locale may drop "raw",
   "uncalibrated", or their equivalents.
2. **No verification metrics** (CRPS, CRPSS, Brier, reliability, coverage,
   leaderboard) are published before the 15-issue-date gate — no locale may
   imply results already exist.
3. **Gaps stay null and are never filled** — no locale may suggest imputation.
4. Dates shown as issue time are always **Argentina time (UTC−3)**.

## Provenance note

Except for `en`, the translations in this app are machine-generated and are
meant to be improved by corrections. The About screen and `docs/` carry the
same notice. Corrections to this glossary take precedence over the ARB files.
