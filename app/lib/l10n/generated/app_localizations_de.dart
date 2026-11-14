// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for German (`de`).
class AppLocalizationsDe extends AppLocalizations {
  AppLocalizationsDe([String locale = 'de']) : super(locale);

  @override
  String get appTitle => 'PRISMA · Vorhersage nach Station';

  @override
  String get appTagline =>
      'Rohes Open-Meteo-Ensemble (GFS und ECMWF IFS) für 19 Stationen in Argentinien.';

  @override
  String get tabStations => 'Stationen';

  @override
  String get tabForecast => 'Vorhersage';

  @override
  String get tabAbout => 'Über / Status';

  @override
  String get searchHint => 'Stationen suchen';

  @override
  String get searchNoResults => 'Keine Station passt zur Suche.';

  @override
  String get stationsIntro =>
      'Wählen Sie eine Station, um ihre Vorhersage zu sehen.';

  @override
  String get clearSearch => 'Löschen';

  @override
  String get retry => 'Erneut versuchen';

  @override
  String get loading => 'Daten werden geladen…';

  @override
  String get labelIssue => 'Abgabe';

  @override
  String get labelExported => 'Exportiert';

  @override
  String get labelSmn => 'SMN-Beobachtungen';

  @override
  String get labelClimateZone => 'Klimazone';

  @override
  String get labelCoordinates => 'Koordinaten';

  @override
  String get argentinaTimeNote => 'Argentinische Zeit (UTC−3)';

  @override
  String get variableT2mMax => 'Tagesmaximum (t2m_max)';

  @override
  String get variableT2mMin => 'Tagesminimum (t2m_min)';

  @override
  String get variablePrecip => 'Niederschlag (Mitgliedsanteil)';

  @override
  String get legendBand1090 => '10–90-%-Band';

  @override
  String get legendBand2575 => '25–75-%-Band';

  @override
  String get legendMedian => 'Median';

  @override
  String get legendModelsNeverPooled =>
      'Jedes Modell behält seine eigenen Mitglieder und seine eigenen Perzentile; sie werden nie zusammengeführt.';

  @override
  String get legendLeadAxis => 'Vorhersagetag';

  @override
  String get noData => 'keine Daten';

  @override
  String get missingMembersTitle => 'Keine Daten';

  @override
  String missingMembers(int members, int nominal) {
    return 'keine Daten ($members/$nominal Mitglieder)';
  }

  @override
  String get observedTitle => 'SMN-Beobachtung — letzte 30 Tage';

  @override
  String get observedNote =>
      'Archivierte Werte, wie vom SMN ausgeliefert; Lücken bleiben null und werden nie gefüllt.';

  @override
  String get observedDate => 'Datum';

  @override
  String get observedMax => 'Max.';

  @override
  String get observedMin => 'Min.';

  @override
  String get precipTitle => 'Niederschlag';

  @override
  String get precipGe1 => '≥ 1 mm';

  @override
  String get precipGe10 => '≥ 10 mm';

  @override
  String get precipNote =>
      'Anteil der nutzbaren Mitglieder mit tagessummiertem Niederschlag über oder gleich dem Schwellwert.';

  @override
  String get day => 'Tag';

  @override
  String get date => 'Datum';

  @override
  String get model => 'Modell';

  @override
  String get rawBanner =>
      'Rohes Ensemble-Vorhersagefeld: nicht bias-korrigiert und nicht kalibriert. Vor dem Schwellwert von 15 Abgabedaten werden keine Verifikationsmetriken veröffentlicht.';

  @override
  String get attributionTitle => 'Daten und Attribution';

  @override
  String get attributionObserved =>
      'Beobachtete Reihen: Servicio Meteorológico Nacional, archiviert wie ausgeliefert; Lücken bleiben null und werden nie gefüllt.';

  @override
  String get attributionNote =>
      'Attributionszeilen werden wörtlich wiedergegeben, wie es ihre Lizenzen verlangen; nur die umgebende Erklärung wird übersetzt.';

  @override
  String get aboutTitle => 'Über / Status';

  @override
  String get aboutWhatTitle => 'Was diese App zeigt';

  @override
  String get aboutWhat =>
      'PRISMA veröffentlicht für 19 Stationen in Argentinien die rohe probabilistische Vorhersage zweier Ensembles (ECMWF IFS und GFS) bis zu 15 Vorhersagetagen sowie die vom SMN in den letzten 30 Tagen beobachteten Höchst- und Tiefsttemperaturen. Die App liest ausschließlich statische Dateien auf GitHub Pages: es gibt keinen Server und keine API.';

  @override
  String get aboutNoSkillTitle => 'Keine Skill-Metriken';

  @override
  String get aboutNoSkill =>
      'Die App zeigt weder CRPS noch CRPSS, Brier-Score, Zuverlässigkeit, Abdeckung oder eine Rangliste. Diese Zahlen werden vor dem Schwellwert von 15 Abgabedaten nicht veröffentlicht.';

  @override
  String get aboutStatusTitle => 'Datenstatus';

  @override
  String get aboutSourcesTitle => 'Quellen und Lizenzen';

  @override
  String get aboutDataset => 'Datensatz';

  @override
  String get aboutSmnSnapshot => 'SMN-Snapshot (regtemp)';

  @override
  String get aboutRegion => 'Region';

  @override
  String get aboutSchema => 'Schema';

  @override
  String get statusForecasts =>
      'Mitglieder des rohen Ensembles: nicht bias-korrigiert, nicht kalibriert und über das Qualitätsflag der Quelle hinaus nicht qualitätskontrolliert.';

  @override
  String get statusVerification =>
      'Vor dem Schwellwert von 15 Abgabedaten in docs/EVALUATION_PROTOCOL.md werden keine Verifikationsergebnisse (CRPS, CRPSS, Brier, Zuverlässigkeit, Abdeckung, Rangliste) veröffentlicht.';

  @override
  String get statusObservations =>
      'Der SMN-Regtemp-Snapshot wird archiviert wie ausgeliefert; Lücken bleiben null und werden nie gefüllt. Die Produktvorrangregel vom 2026-11-14 gilt (regtemp primär).';

  @override
  String get aboutMachineTranslations =>
      'Übersetzungen außer Englisch sind maschinell erzeugt; Korrekturen und Verbesserungen sind willkommen.';

  @override
  String get languageLabel => 'Sprache';

  @override
  String leadDay(int lead) {
    return '+$lead d';
  }

  @override
  String errorTitle(String document) {
    return 'Dokument $document konnte nicht gelesen werden';
  }

  @override
  String schemaUnsupported(String version) {
    return 'Schema-Version \"$version\" wird von dieser App nicht unterstützt (erwartet 1.0). Aktualisieren Sie die App oder den Export.';
  }

  @override
  String parseError(String document, String detail) {
    return 'Dokument $document hat nicht das erwartete Format: $detail';
  }

  @override
  String networkError(String document, String detail) {
    return 'Dokument $document konnte nicht heruntergeladen werden: $detail';
  }

  @override
  String httpError(int status, String document) {
    return 'Die Datenquelle hat HTTP $status für $document zurückgegeben.';
  }

  @override
  String invalidJson(String document, String detail) {
    return 'Ungültiges JSON in $document: $detail';
  }

  @override
  String get modelsNonText =>
      'Das Feld \"models\" enthält einen Nicht-Textwert.';

  @override
  String fieldNotObject(String field) {
    return 'Feld \"$field\" ist kein JSON-Objekt.';
  }

  @override
  String fieldNotArray(String field) {
    return 'Feld \"$field\" ist kein JSON-Array.';
  }

  @override
  String missingTextField(String field) {
    return 'Textfeld \"$field\" fehlt oder ist kein String.';
  }

  @override
  String missingIntegerField(String field) {
    return 'Ganzzahl \"$field\" fehlt oder ist keine Zahl.';
  }

  @override
  String notNumericField(String field) {
    return 'Feld \"$field\" ist nicht numerisch.';
  }

  @override
  String missingSchemaVersion(String document) {
    return 'Feld schema_version fehlt in $document.';
  }

  @override
  String stationCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count Stationen',
      one: '$count Station',
    );
    return '$_temp0';
  }

  @override
  String get stationsViewList => 'Liste';

  @override
  String get stationsViewMap => 'Karte';

  @override
  String get stationsViewForecast => 'Vorhersage ansehen';

  @override
  String get mapLegend => 'Legende';

  @override
  String get mapReportProblem => 'Kartenproblem melden';

  @override
  String get mapTilesFailed =>
      'Kartenkacheln konnten nicht geladen werden. Stationen werden auf neutralem Hintergrund angezeigt.';

  @override
  String get aboutMapTilesTitle => 'Kartenkacheln';

  @override
  String get aboutMapTilesNote =>
      'Die Karte laedt ihre Kacheln direkt von den OpenStreetMap-Servern.';
}
