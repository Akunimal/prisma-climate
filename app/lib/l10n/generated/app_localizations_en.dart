// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'PRISMA · Forecast by station';

  @override
  String get appTagline =>
      'Raw Open-Meteo ensemble (GFS and ECMWF IFS) for 19 stations in Argentina.';

  @override
  String get tabStations => 'Stations';

  @override
  String get tabForecast => 'Forecast';

  @override
  String get tabSkill => 'Skill';

  @override
  String get tabAbout => 'About / Status';

  @override
  String get searchHint => 'Search stations or places';

  @override
  String get searchNoResults => 'No stations match the search.';

  @override
  String get stationsIntro => 'Pick a station to see its forecast.';

  @override
  String get clearSearch => 'Clear';

  @override
  String get retry => 'Retry';

  @override
  String get loading => 'Loading data…';

  @override
  String get labelIssue => 'Issue';

  @override
  String get labelExported => 'Exported';

  @override
  String get labelSmn => 'SMN observations';

  @override
  String get labelClimateZone => 'Climate zone';

  @override
  String get labelCoordinates => 'Coordinates';

  @override
  String get argentinaTimeNote => 'Argentina time (UTC−3)';

  @override
  String get variableT2mMax => 'Daily maximum (t2m_max)';

  @override
  String get variableT2mMin => 'Daily minimum (t2m_min)';

  @override
  String get variablePrecip => 'Precipitation (member fraction)';

  @override
  String get legendBand1090 => '10–90 % band';

  @override
  String get legendBand2575 => '25–75 % band';

  @override
  String get legendMedian => 'Median';

  @override
  String get legendModelsNeverPooled =>
      'Each model keeps its own members and its own percentiles; they are never pooled.';

  @override
  String get legendLeadAxis => 'Lead day';

  @override
  String get noData => 'no data';

  @override
  String get missingMembersTitle => 'No data';

  @override
  String missingMembers(int members, int nominal) {
    return 'no data ($members/$nominal members)';
  }

  @override
  String get observedTitle => 'SMN observed — last 30 days';

  @override
  String get observedNote =>
      'Archived values as served by SMN; gaps stay null and are never filled.';

  @override
  String get observedDate => 'Date';

  @override
  String get observedMax => 'Max';

  @override
  String get observedMin => 'Min';

  @override
  String get precipTitle => 'Precipitation';

  @override
  String get precipGe1 => '≥ 1 mm';

  @override
  String get precipGe10 => '≥ 10 mm';

  @override
  String get precipNote =>
      'Fraction of usable members with daily accumulated precipitation at or above the threshold.';

  @override
  String get day => 'Day';

  @override
  String get date => 'Date';

  @override
  String get model => 'Model';

  @override
  String get rawBanner =>
      'Raw ensemble forecast: not bias-corrected and not calibrated. No verification metrics are published before the 15-issue-date gate.';

  @override
  String get attributionTitle => 'Data and attribution';

  @override
  String get attributionObserved =>
      'Observed series: Servicio Meteorológico Nacional, archived as served; gaps stay null and are never filled.';

  @override
  String get attributionNote =>
      'Attribution lines are reproduced verbatim as their licences require; only the surrounding explanation is translated.';

  @override
  String get aboutTitle => 'About / Status';

  @override
  String get aboutWhatTitle => 'What this app shows';

  @override
  String get aboutWhat =>
      'PRISMA publishes, for 19 stations in Argentina, the raw probabilistic forecast of two ensembles (ECMWF IFS and GFS) up to 15 days ahead, plus the daily maximum and minimum temperatures observed by SMN over the last 30 days. The app reads only static files published on GitHub Pages: there is no server and no API.';

  @override
  String get aboutNoSkillTitle => 'Operational skill metrics';

  @override
  String get aboutNoSkill =>
      'Operational verification results (CRPS, CRPSS, Brier, reliability, coverage, leaderboard) are not published before the 15-issue-date gate. The Skill screen shows only hindcast-labelled calibration scores from a historical replay; they are never mixed with the operational archive.';

  @override
  String get skillTitle => 'Calibration skill (hindcast)';

  @override
  String get skillHindcastBanner =>
      'Hindcast only: these scores come from a historical replay against archived observations, not from the live forecast archive. They are never mixed with operational verification.';

  @override
  String get skillUnavailable =>
      'No hindcast calibration run is available yet.';

  @override
  String get skillLabel => 'Label';

  @override
  String get skillMeanEmos => 'Mean CRPSS (EMOS vs raw)';

  @override
  String get skillMeanQm => 'Mean CRPSS (QM vs raw)';

  @override
  String skillCellsCount(int sufficient, int total) {
    return '$sufficient of $total cells with enough training data';
  }

  @override
  String get skillDidNotBeat =>
      'Mean CRPSS ≤ 0: on this hindcast window calibration did not beat the raw ensemble.';

  @override
  String get skillProvider => 'Provider';

  @override
  String get skillWindow => 'Window';

  @override
  String get skillRetrieved => 'Retrieved';

  @override
  String get skillLeads => 'Leads';

  @override
  String get skillMode => 'Mode';

  @override
  String get skillGateTitle => 'Operational gate';

  @override
  String skillGateArchived(int archived, int required) {
    return 'Archived issue dates: $archived of $required';
  }

  @override
  String get skillGateOpen =>
      'Gate open — operational leaderboard may be published.';

  @override
  String get skillGateClosed =>
      'Gate closed — operational leaderboard is not published.';

  @override
  String get skillCellsTitle => 'Cells by station and lead';

  @override
  String get skillCellStation => 'Station';

  @override
  String get comparatorTitle => 'Source comparison';

  @override
  String get comparatorNote =>
      'Daily maximum percentiles side by side per model (°C): p10–p90 · median. Never pooled.';

  @override
  String get aboutStatusTitle => 'Data status';

  @override
  String get aboutSourcesTitle => 'Sources and licences';

  @override
  String get aboutDataset => 'Dataset';

  @override
  String get aboutSmnSnapshot => 'SMN snapshot (regtemp)';

  @override
  String get aboutRegion => 'Region';

  @override
  String get aboutSchema => 'Schema';

  @override
  String get statusForecasts =>
      'Raw ensemble members: not bias-corrected, not calibrated, and not quality-controlled beyond the source quality flag.';

  @override
  String get statusVerification =>
      'No verification results (CRPS, CRPSS, Brier, reliability, coverage, leaderboard) are published before the 15-issue-date gate in docs/EVALUATION_PROTOCOL.md.';

  @override
  String get statusObservations =>
      'The SMN regtemp snapshot is archived as served; gaps stay null and are never filled. The 2026-11-14 product precedence rule applies (regtemp primary).';

  @override
  String get aboutMachineTranslations =>
      'Translations other than English are machine-generated; corrections and improvements are welcome.';

  @override
  String get languageLabel => 'Language';

  @override
  String leadDay(int lead) {
    return '+$lead d';
  }

  @override
  String errorTitle(String document) {
    return 'Could not read $document';
  }

  @override
  String schemaUnsupported(String version) {
    return 'Schema version \"$version\" is not supported by this app (expected 1.0). Update the app or the export.';
  }

  @override
  String parseError(String document, String detail) {
    return 'Document $document is not in the expected format: $detail';
  }

  @override
  String networkError(String document, String detail) {
    return 'Could not download $document: $detail';
  }

  @override
  String httpError(int status, String document) {
    return 'The data source returned HTTP $status for $document.';
  }

  @override
  String invalidJson(String document, String detail) {
    return 'Invalid JSON in $document: $detail';
  }

  @override
  String get modelsNonText => 'The \"models\" field contains a non-text value.';

  @override
  String fieldNotObject(String field) {
    return 'Field \"$field\" is not a JSON object.';
  }

  @override
  String fieldNotArray(String field) {
    return 'Field \"$field\" is not a JSON array.';
  }

  @override
  String missingTextField(String field) {
    return 'Missing text field \"$field\" or it is not a string.';
  }

  @override
  String missingIntegerField(String field) {
    return 'Missing integer \"$field\" or it is not a number.';
  }

  @override
  String notNumericField(String field) {
    return 'Field \"$field\" is not numeric.';
  }

  @override
  String missingSchemaVersion(String document) {
    return 'Missing schema_version field in $document.';
  }

  @override
  String stationCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count stations',
      one: '1 station',
    );
    return '$_temp0';
  }

  @override
  String get stationsViewList => 'List';

  @override
  String get stationsViewMap => 'Map';

  @override
  String get stationsViewForecast => 'View forecast';

  @override
  String get mapLegend => 'Legend';

  @override
  String get mapReportProblem => 'Report a map problem';

  @override
  String get mapTilesFailed =>
      'Map tiles could not be loaded. Showing stations on a neutral background.';

  @override
  String get aboutMapTilesTitle => 'Map tiles';

  @override
  String get aboutMapTilesNote =>
      'The map loads its tiles directly from OpenStreetMap servers.';

  @override
  String get searchStationsGroup => 'Stations';

  @override
  String get searchPlacesGroup => 'Places';

  @override
  String get placesUnavailable => 'Place search is unavailable right now.';

  @override
  String nearestStation(String station) {
    return 'Nearest station: $station';
  }

  @override
  String distanceKm(String km) {
    return 'Distance: $km km';
  }

  @override
  String get nearestStationWarning =>
      'No station within 100 km — the forecast is for the nearest station, which may not represent your location.';

  @override
  String get useMyLocation => 'Use my location';

  @override
  String get locationDenied =>
      'Location permission denied. Search for a place instead.';

  @override
  String get locationUnavailable => 'Location is not available on this device.';

  @override
  String get locationTimeout =>
      'Could not get your location. Try again or search for a place.';

  @override
  String get yourLocation => 'Your location';

  @override
  String get aboutPlacesTitle => 'Place data';

  @override
  String get aboutPlacesNote =>
      'Place names come from GeoNames and are used only for search on this device.';

  @override
  String get aboutPrivacyTitle => 'Privacy';

  @override
  String get aboutPrivacyNote =>
      'Place search and location stay on this device; only map tiles are requested from the map provider.';
}
