import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_de.dart';
import 'app_localizations_en.dart';
import 'app_localizations_es.dart';
import 'app_localizations_fr.dart';
import 'app_localizations_hi.dart';
import 'app_localizations_it.dart';
import 'app_localizations_ja.dart';
import 'app_localizations_pt.dart';
import 'app_localizations_ru.dart';
import 'app_localizations_zh.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'generated/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('de'),
    Locale('en'),
    Locale('es'),
    Locale('fr'),
    Locale('hi'),
    Locale('it'),
    Locale('ja'),
    Locale('pt'),
    Locale('ru'),
    Locale('zh'),
  ];

  /// No description provided for @appTitle.
  ///
  /// In en, this message translates to:
  /// **'PRISMA · Forecast by station'**
  String get appTitle;

  /// No description provided for @appTagline.
  ///
  /// In en, this message translates to:
  /// **'Raw Open-Meteo ensemble (GFS and ECMWF IFS) for 19 stations in Argentina.'**
  String get appTagline;

  /// No description provided for @tabStations.
  ///
  /// In en, this message translates to:
  /// **'Stations'**
  String get tabStations;

  /// No description provided for @tabForecast.
  ///
  /// In en, this message translates to:
  /// **'Forecast'**
  String get tabForecast;

  /// No description provided for @tabAbout.
  ///
  /// In en, this message translates to:
  /// **'About / Status'**
  String get tabAbout;

  /// No description provided for @searchHint.
  ///
  /// In en, this message translates to:
  /// **'Search stations'**
  String get searchHint;

  /// No description provided for @searchNoResults.
  ///
  /// In en, this message translates to:
  /// **'No stations match the search.'**
  String get searchNoResults;

  /// No description provided for @stationsIntro.
  ///
  /// In en, this message translates to:
  /// **'Pick a station to see its forecast.'**
  String get stationsIntro;

  /// No description provided for @clearSearch.
  ///
  /// In en, this message translates to:
  /// **'Clear'**
  String get clearSearch;

  /// No description provided for @retry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get retry;

  /// No description provided for @loading.
  ///
  /// In en, this message translates to:
  /// **'Loading data…'**
  String get loading;

  /// No description provided for @labelIssue.
  ///
  /// In en, this message translates to:
  /// **'Issue'**
  String get labelIssue;

  /// No description provided for @labelExported.
  ///
  /// In en, this message translates to:
  /// **'Exported'**
  String get labelExported;

  /// No description provided for @labelSmn.
  ///
  /// In en, this message translates to:
  /// **'SMN observations'**
  String get labelSmn;

  /// No description provided for @labelClimateZone.
  ///
  /// In en, this message translates to:
  /// **'Climate zone'**
  String get labelClimateZone;

  /// No description provided for @labelCoordinates.
  ///
  /// In en, this message translates to:
  /// **'Coordinates'**
  String get labelCoordinates;

  /// No description provided for @argentinaTimeNote.
  ///
  /// In en, this message translates to:
  /// **'Argentina time (UTC−3)'**
  String get argentinaTimeNote;

  /// No description provided for @variableT2mMax.
  ///
  /// In en, this message translates to:
  /// **'Daily maximum (t2m_max)'**
  String get variableT2mMax;

  /// No description provided for @variableT2mMin.
  ///
  /// In en, this message translates to:
  /// **'Daily minimum (t2m_min)'**
  String get variableT2mMin;

  /// No description provided for @variablePrecip.
  ///
  /// In en, this message translates to:
  /// **'Precipitation (member fraction)'**
  String get variablePrecip;

  /// No description provided for @legendBand1090.
  ///
  /// In en, this message translates to:
  /// **'10–90 % band'**
  String get legendBand1090;

  /// No description provided for @legendBand2575.
  ///
  /// In en, this message translates to:
  /// **'25–75 % band'**
  String get legendBand2575;

  /// No description provided for @legendMedian.
  ///
  /// In en, this message translates to:
  /// **'Median'**
  String get legendMedian;

  /// No description provided for @legendModelsNeverPooled.
  ///
  /// In en, this message translates to:
  /// **'Each model keeps its own members and its own percentiles; they are never pooled.'**
  String get legendModelsNeverPooled;

  /// No description provided for @legendLeadAxis.
  ///
  /// In en, this message translates to:
  /// **'Lead day'**
  String get legendLeadAxis;

  /// No description provided for @noData.
  ///
  /// In en, this message translates to:
  /// **'no data'**
  String get noData;

  /// No description provided for @missingMembersTitle.
  ///
  /// In en, this message translates to:
  /// **'No data'**
  String get missingMembersTitle;

  /// No description provided for @missingMembers.
  ///
  /// In en, this message translates to:
  /// **'no data ({members}/{nominal} members)'**
  String missingMembers(int members, int nominal);

  /// No description provided for @observedTitle.
  ///
  /// In en, this message translates to:
  /// **'SMN observed — last 30 days'**
  String get observedTitle;

  /// No description provided for @observedNote.
  ///
  /// In en, this message translates to:
  /// **'Archived values as served by SMN; gaps stay null and are never filled.'**
  String get observedNote;

  /// No description provided for @observedDate.
  ///
  /// In en, this message translates to:
  /// **'Date'**
  String get observedDate;

  /// No description provided for @observedMax.
  ///
  /// In en, this message translates to:
  /// **'Max'**
  String get observedMax;

  /// No description provided for @observedMin.
  ///
  /// In en, this message translates to:
  /// **'Min'**
  String get observedMin;

  /// No description provided for @precipTitle.
  ///
  /// In en, this message translates to:
  /// **'Precipitation'**
  String get precipTitle;

  /// No description provided for @precipGe1.
  ///
  /// In en, this message translates to:
  /// **'≥ 1 mm'**
  String get precipGe1;

  /// No description provided for @precipGe10.
  ///
  /// In en, this message translates to:
  /// **'≥ 10 mm'**
  String get precipGe10;

  /// No description provided for @precipNote.
  ///
  /// In en, this message translates to:
  /// **'Fraction of usable members with daily accumulated precipitation at or above the threshold.'**
  String get precipNote;

  /// No description provided for @day.
  ///
  /// In en, this message translates to:
  /// **'Day'**
  String get day;

  /// No description provided for @date.
  ///
  /// In en, this message translates to:
  /// **'Date'**
  String get date;

  /// No description provided for @model.
  ///
  /// In en, this message translates to:
  /// **'Model'**
  String get model;

  /// No description provided for @rawBanner.
  ///
  /// In en, this message translates to:
  /// **'Raw ensemble forecast: not bias-corrected and not calibrated. No verification metrics are published before the 15-issue-date gate.'**
  String get rawBanner;

  /// No description provided for @attributionTitle.
  ///
  /// In en, this message translates to:
  /// **'Data and attribution'**
  String get attributionTitle;

  /// No description provided for @attributionObserved.
  ///
  /// In en, this message translates to:
  /// **'Observed series: Servicio Meteorológico Nacional, archived as served; gaps stay null and are never filled.'**
  String get attributionObserved;

  /// No description provided for @attributionNote.
  ///
  /// In en, this message translates to:
  /// **'Attribution lines are reproduced verbatim as their licences require; only the surrounding explanation is translated.'**
  String get attributionNote;

  /// No description provided for @aboutTitle.
  ///
  /// In en, this message translates to:
  /// **'About / Status'**
  String get aboutTitle;

  /// No description provided for @aboutWhatTitle.
  ///
  /// In en, this message translates to:
  /// **'What this app shows'**
  String get aboutWhatTitle;

  /// No description provided for @aboutWhat.
  ///
  /// In en, this message translates to:
  /// **'PRISMA publishes, for 19 stations in Argentina, the raw probabilistic forecast of two ensembles (ECMWF IFS and GFS) up to 15 days ahead, plus the daily maximum and minimum temperatures observed by SMN over the last 30 days. The app reads only static files published on GitHub Pages: there is no server and no API.'**
  String get aboutWhat;

  /// No description provided for @aboutNoSkillTitle.
  ///
  /// In en, this message translates to:
  /// **'No skill metrics'**
  String get aboutNoSkillTitle;

  /// No description provided for @aboutNoSkill.
  ///
  /// In en, this message translates to:
  /// **'The app shows no CRPS, CRPSS, Brier score, reliability, coverage or leaderboard. Those numbers are not published before the 15-issue-date gate.'**
  String get aboutNoSkill;

  /// No description provided for @aboutStatusTitle.
  ///
  /// In en, this message translates to:
  /// **'Data status'**
  String get aboutStatusTitle;

  /// No description provided for @aboutSourcesTitle.
  ///
  /// In en, this message translates to:
  /// **'Sources and licences'**
  String get aboutSourcesTitle;

  /// No description provided for @aboutDataset.
  ///
  /// In en, this message translates to:
  /// **'Dataset'**
  String get aboutDataset;

  /// No description provided for @aboutSmnSnapshot.
  ///
  /// In en, this message translates to:
  /// **'SMN snapshot (regtemp)'**
  String get aboutSmnSnapshot;

  /// No description provided for @aboutRegion.
  ///
  /// In en, this message translates to:
  /// **'Region'**
  String get aboutRegion;

  /// No description provided for @aboutSchema.
  ///
  /// In en, this message translates to:
  /// **'Schema'**
  String get aboutSchema;

  /// No description provided for @statusForecasts.
  ///
  /// In en, this message translates to:
  /// **'Raw ensemble members: not bias-corrected, not calibrated, and not quality-controlled beyond the source quality flag.'**
  String get statusForecasts;

  /// No description provided for @statusVerification.
  ///
  /// In en, this message translates to:
  /// **'No verification results (CRPS, CRPSS, Brier, reliability, coverage, leaderboard) are published before the 15-issue-date gate in docs/EVALUATION_PROTOCOL.md.'**
  String get statusVerification;

  /// No description provided for @statusObservations.
  ///
  /// In en, this message translates to:
  /// **'The SMN regtemp snapshot is archived as served; gaps stay null and are never filled. The 2026-11-14 product precedence rule applies (regtemp primary).'**
  String get statusObservations;

  /// No description provided for @aboutMachineTranslations.
  ///
  /// In en, this message translates to:
  /// **'Translations other than English are machine-generated; corrections and improvements are welcome.'**
  String get aboutMachineTranslations;

  /// No description provided for @languageLabel.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get languageLabel;

  /// No description provided for @leadDay.
  ///
  /// In en, this message translates to:
  /// **'+{lead} d'**
  String leadDay(int lead);

  /// No description provided for @errorTitle.
  ///
  /// In en, this message translates to:
  /// **'Could not read {document}'**
  String errorTitle(String document);

  /// No description provided for @schemaUnsupported.
  ///
  /// In en, this message translates to:
  /// **'Schema version \"{version}\" is not supported by this app (expected 1.0). Update the app or the export.'**
  String schemaUnsupported(String version);

  /// No description provided for @parseError.
  ///
  /// In en, this message translates to:
  /// **'Document {document} is not in the expected format: {detail}'**
  String parseError(String document, String detail);

  /// No description provided for @networkError.
  ///
  /// In en, this message translates to:
  /// **'Could not download {document}: {detail}'**
  String networkError(String document, String detail);

  /// No description provided for @httpError.
  ///
  /// In en, this message translates to:
  /// **'The data source returned HTTP {status} for {document}.'**
  String httpError(int status, String document);

  /// No description provided for @invalidJson.
  ///
  /// In en, this message translates to:
  /// **'Invalid JSON in {document}: {detail}'**
  String invalidJson(String document, String detail);

  /// No description provided for @modelsNonText.
  ///
  /// In en, this message translates to:
  /// **'The \"models\" field contains a non-text value.'**
  String get modelsNonText;

  /// No description provided for @fieldNotObject.
  ///
  /// In en, this message translates to:
  /// **'Field \"{field}\" is not a JSON object.'**
  String fieldNotObject(String field);

  /// No description provided for @fieldNotArray.
  ///
  /// In en, this message translates to:
  /// **'Field \"{field}\" is not a JSON array.'**
  String fieldNotArray(String field);

  /// No description provided for @missingTextField.
  ///
  /// In en, this message translates to:
  /// **'Missing text field \"{field}\" or it is not a string.'**
  String missingTextField(String field);

  /// No description provided for @missingIntegerField.
  ///
  /// In en, this message translates to:
  /// **'Missing integer \"{field}\" or it is not a number.'**
  String missingIntegerField(String field);

  /// No description provided for @notNumericField.
  ///
  /// In en, this message translates to:
  /// **'Field \"{field}\" is not numeric.'**
  String notNumericField(String field);

  /// No description provided for @missingSchemaVersion.
  ///
  /// In en, this message translates to:
  /// **'Missing schema_version field in {document}.'**
  String missingSchemaVersion(String document);

  /// No description provided for @stationCount.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{1 station} other{{count} stations}}'**
  String stationCount(int count);

  /// No description provided for @stationsViewList.
  ///
  /// In en, this message translates to:
  /// **'List'**
  String get stationsViewList;

  /// No description provided for @stationsViewMap.
  ///
  /// In en, this message translates to:
  /// **'Map'**
  String get stationsViewMap;

  /// No description provided for @stationsViewForecast.
  ///
  /// In en, this message translates to:
  /// **'View forecast'**
  String get stationsViewForecast;

  /// No description provided for @mapLegend.
  ///
  /// In en, this message translates to:
  /// **'Legend'**
  String get mapLegend;

  /// No description provided for @mapReportProblem.
  ///
  /// In en, this message translates to:
  /// **'Report a map problem'**
  String get mapReportProblem;

  /// No description provided for @mapTilesFailed.
  ///
  /// In en, this message translates to:
  /// **'Map tiles could not be loaded. Showing stations on a neutral background.'**
  String get mapTilesFailed;

  /// No description provided for @aboutMapTilesTitle.
  ///
  /// In en, this message translates to:
  /// **'Map tiles'**
  String get aboutMapTilesTitle;

  /// No description provided for @aboutMapTilesNote.
  ///
  /// In en, this message translates to:
  /// **'The map loads its tiles directly from OpenStreetMap servers.'**
  String get aboutMapTilesNote;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) => <String>[
    'de',
    'en',
    'es',
    'fr',
    'hi',
    'it',
    'ja',
    'pt',
    'ru',
    'zh',
  ].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'de':
      return AppLocalizationsDe();
    case 'en':
      return AppLocalizationsEn();
    case 'es':
      return AppLocalizationsEs();
    case 'fr':
      return AppLocalizationsFr();
    case 'hi':
      return AppLocalizationsHi();
    case 'it':
      return AppLocalizationsIt();
    case 'ja':
      return AppLocalizationsJa();
    case 'pt':
      return AppLocalizationsPt();
    case 'ru':
      return AppLocalizationsRu();
    case 'zh':
      return AppLocalizationsZh();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
