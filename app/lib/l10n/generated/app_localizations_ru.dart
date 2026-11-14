// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Russian (`ru`).
class AppLocalizationsRu extends AppLocalizations {
  AppLocalizationsRu([String locale = 'ru']) : super(locale);

  @override
  String get appTitle => 'PRISMA · Прогноз по станции';

  @override
  String get appTagline =>
      'Сырой ансамбль Open-Meteo (GFS и ECMWF IFS) для 19 станций Аргентины.';

  @override
  String get tabStations => 'Станции';

  @override
  String get tabForecast => 'Прогноз';

  @override
  String get tabAbout => 'О приложении / Статус';

  @override
  String get searchHint => 'Поиск станций';

  @override
  String get searchNoResults => 'Ни одна станция не подходит под запрос.';

  @override
  String get stationsIntro => 'Выберите станцию, чтобы увидеть её прогноз.';

  @override
  String get clearSearch => 'Очистить';

  @override
  String get retry => 'Повторить';

  @override
  String get loading => 'Загрузка данных…';

  @override
  String get labelIssue => 'Выпуск';

  @override
  String get labelExported => 'Экспортировано';

  @override
  String get labelSmn => 'Наблюдения SMN';

  @override
  String get labelClimateZone => 'Климатическая зона';

  @override
  String get labelCoordinates => 'Координаты';

  @override
  String get argentinaTimeNote => 'Время Аргентины (UTC−3)';

  @override
  String get variableT2mMax => 'Дневной максимум (t2m_max)';

  @override
  String get variableT2mMin => 'Дневной минимум (t2m_min)';

  @override
  String get variablePrecip => 'Осадки (доля членов)';

  @override
  String get legendBand1090 => 'Полоса 10–90 %';

  @override
  String get legendBand2575 => 'Полоса 25–75 %';

  @override
  String get legendMedian => 'Медиана';

  @override
  String get legendModelsNeverPooled =>
      'Каждая модель сохраняет собственные члены и собственные процентили; они никогда не объединяются.';

  @override
  String get legendLeadAxis => 'День прогноза';

  @override
  String get noData => 'нет данных';

  @override
  String get missingMembersTitle => 'Нет данных';

  @override
  String missingMembers(int members, int nominal) {
    return 'нет данных ($members/$nominal членов)';
  }

  @override
  String get observedTitle => 'Наблюдения SMN — последние 30 дней';

  @override
  String get observedNote =>
      'Архивные значения, как их отдаёт SMN; пропуски остаются null и никогда не заполняются.';

  @override
  String get observedDate => 'Дата';

  @override
  String get observedMax => 'Макс.';

  @override
  String get observedMin => 'Мин.';

  @override
  String get precipTitle => 'Осадки';

  @override
  String get precipGe1 => '≥ 1 mm';

  @override
  String get precipGe10 => '≥ 10 mm';

  @override
  String get precipNote =>
      'Доля пригодных членов с суточными осадками на уровне или выше порога.';

  @override
  String get day => 'День';

  @override
  String get date => 'Дата';

  @override
  String get model => 'Модель';

  @override
  String get rawBanner =>
      'Сырой ансамблевый прогноз: без коррекции смещения и без калибровки. Метрики верификации не публикуются до порога в 15 дат выпуска.';

  @override
  String get attributionTitle => 'Данные и атрибуция';

  @override
  String get attributionObserved =>
      'Ряды наблюдений: Servicio Meteorológico Nacional, заархивированы как отданы; пропуски остаются null и никогда не заполняются.';

  @override
  String get attributionNote =>
      'Строки атрибуции воспроизводятся дословно, как того требуют их лицензии; переводится только пояснение вокруг них.';

  @override
  String get aboutTitle => 'О приложении / Статус';

  @override
  String get aboutWhatTitle => 'Что показывает это приложение';

  @override
  String get aboutWhat =>
      'PRISMA публикует для 19 станций Аргентины сырой вероятностный прогноз двух ансамблей (ECMWF IFS и GFS) на срок до 15 дней, а также суточные максимальная и минимальная температуры, наблюдавшиеся SMN за последние 30 дней. Приложение читает только статические файлы на GitHub Pages: сервера и API нет.';

  @override
  String get aboutNoSkillTitle => 'Без метрик skill';

  @override
  String get aboutNoSkill =>
      'Приложение не показывает CRPS, CRPSS, ошибку Бриера, надёжность, покрытие и рейтинг. Эти числа не публикуются до порога в 15 дат выпуска.';

  @override
  String get aboutStatusTitle => 'Статус данных';

  @override
  String get aboutSourcesTitle => 'Источники и лицензии';

  @override
  String get aboutDataset => 'Датасет';

  @override
  String get aboutSmnSnapshot => 'Срез SMN (regtemp)';

  @override
  String get aboutRegion => 'Регион';

  @override
  String get aboutSchema => 'Схема';

  @override
  String get statusForecasts =>
      'Сырые члены ансамбля: без коррекции смещения, без калибровки и без контроля качества, кроме флага качества источника.';

  @override
  String get statusVerification =>
      'Результаты верификации (CRPS, CRPSS, Brier, надёжность, покрытие, рейтинг) не публикуются до порога в 15 дат выпуска в docs/EVALUATION_PROTOCOL.md.';

  @override
  String get statusObservations =>
      'Срез SMN regtemp архивируется как отдан; пропуски остаются null и никогда не заполняются. Действует правило приоритета продуктов от 2026-11-14 (regtemp основной).';

  @override
  String get aboutMachineTranslations =>
      'Переводы на языки, отличные от английского, сгенерированы машиной; исправления и улучшения приветствуются.';

  @override
  String get languageLabel => 'Язык';

  @override
  String leadDay(int lead) {
    return '+$lead d';
  }

  @override
  String errorTitle(String document) {
    return 'Не удалось прочитать $document';
  }

  @override
  String schemaUnsupported(String version) {
    return 'Версия схемы \"$version\" не поддерживается этим приложением (ожидается 1.0). Обновите приложение или экспорт.';
  }

  @override
  String parseError(String document, String detail) {
    return 'Документ $document имеет неожиданный формат: $detail';
  }

  @override
  String networkError(String document, String detail) {
    return 'Не удалось скачать $document: $detail';
  }

  @override
  String httpError(int status, String document) {
    return 'Источник данных вернул HTTP $status для $document.';
  }

  @override
  String invalidJson(String document, String detail) {
    return 'Некорректный JSON в $document: $detail';
  }

  @override
  String get modelsNonText => 'Поле \"models\" содержит нетекстовое значение.';

  @override
  String fieldNotObject(String field) {
    return 'Поле \"$field\" не является JSON-объектом.';
  }

  @override
  String fieldNotArray(String field) {
    return 'Поле \"$field\" не является JSON-массивом.';
  }

  @override
  String missingTextField(String field) {
    return 'Отсутствует текстовое поле \"$field\" или оно не строка.';
  }

  @override
  String missingIntegerField(String field) {
    return 'Отсутствует целое \"$field\" или это не число.';
  }

  @override
  String notNumericField(String field) {
    return 'Поле \"$field\" не числовое.';
  }

  @override
  String missingSchemaVersion(String document) {
    return 'В $document отсутствует поле schema_version.';
  }

  @override
  String stationCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count станции',
      many: '$count станций',
      few: '$count станции',
      one: '$count станция',
    );
    return '$_temp0';
  }

  @override
  String get stationsViewList => 'Список';

  @override
  String get stationsViewMap => 'Карта';

  @override
  String get stationsViewForecast => 'Смотреть прогноз';

  @override
  String get mapLegend => 'Легенда';

  @override
  String get mapReportProblem => 'Сообщить о проблеме карты';

  @override
  String get mapTilesFailed =>
      'Не удалось загрузить тайлы карты. Станции показаны на нейтральном фоне.';

  @override
  String get aboutMapTilesTitle => 'Тайлы карты';

  @override
  String get aboutMapTilesNote =>
      'Карта загружает тайлы напрямую с серверов OpenStreetMap.';
}
