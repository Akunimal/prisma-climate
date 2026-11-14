/// Every user-facing string of the app lives here so another language can be
/// added later without touching the widgets.
class S {
  const S._();

  static const String appTitle = 'PRISMA · Forecast by station';
  static const String appTagline =
      'Raw Open-Meteo ensemble (GFS and ECMWF IFS) for 19 stations in Argentina.';

  static const String tabStations = 'Stations';
  static const String tabForecast = 'Forecast';
  static const String tabAbout = 'About / Status';

  static const String searchHint = 'Search stations';
  static const String searchNoResults = 'No stations match the search.';
  static const String stationsIntro = 'Pick a station to see its forecast.';
  static const String clearSearch = 'Clear';

  static const String retry = 'Retry';
  static const String loading = 'Loading data…';

  static const String labelIssue = 'Issue';
  static const String labelExported = 'Exported';
  static const String labelSmn = 'SMN observations';
  static const String labelClimateZone = 'Climate zone';
  static const String labelCoordinates = 'Coordinates';
  static const String argentinaTimeNote = 'Argentina time (UTC−3)';

  static const String variableT2mMax = 'Daily maximum (t2m_max)';
  static const String variableT2mMin = 'Daily minimum (t2m_min)';
  static const String variablePrecip = 'Precipitation (member fraction)';

  static const String legendBand1090 = '10–90 % band';
  static const String legendBand2575 = '25–75 % band';
  static const String legendMedian = 'Median';
  static const String legendModelsNeverPooled =
      'Each model keeps its own members and its own percentiles; they are never pooled.';
  static const String legendLeadAxis = 'Lead day';

  static const String noData = 'no data';
  static const String missingMembersTitle = 'No data';

  static const String observedTitle = 'SMN observed — last 30 days';
  static const String observedNote =
      'Archived values as served by SMN; gaps stay null and are never filled.';
  static const String observedDate = 'Date';
  static const String observedMax = 'Max';
  static const String observedMin = 'Min';

  static const String precipTitle = 'Precipitation';
  static const String precipGe1 = '≥ 1 mm';
  static const String precipGe10 = '≥ 10 mm';
  static const String precipNote =
      'Fraction of usable members with daily accumulated precipitation at or above the threshold.';
  static const String day = 'Day';
  static const String date = 'Date';
  static const String model = 'Model';

  static const String rawBanner =
      'Raw ensemble forecast: not bias-corrected and not calibrated. '
      'No verification metrics are published before the 15-issue-date gate.';

  static const String attributionTitle = 'Data and attribution';
  static const String attributionObserved =
      'Observed series: Servicio Meteorológico Nacional, archived as served; '
      'gaps stay null and are never filled.';

  static const String aboutTitle = 'About / Status';
  static const String aboutWhatTitle = 'What this app shows';
  static const String aboutWhat =
      'PRISMA publishes, for 19 stations in Argentina, the raw probabilistic forecast of two '
      'ensembles (ECMWF IFS and GFS) up to 15 days ahead, plus the daily maximum and minimum '
      'temperatures observed by SMN over the last 30 days. The app reads only static files '
      'published on GitHub Pages: there is no server and no API.';
  static const String aboutNoSkillTitle = 'No skill metrics';
  static const String aboutNoSkill =
      'The app shows no CRPS, CRPSS, Brier score, reliability, coverage or leaderboard. '
      'Those numbers are not published before the 15-issue-date gate.';
  static const String aboutStatusTitle = 'Data status';
  static const String aboutSourcesTitle = 'Sources and licences';
  static const String aboutDataset = 'Dataset';
  static const String aboutSmnSnapshot = 'SMN snapshot (regtemp)';
  static const String aboutRegion = 'Region';
  static const String aboutSchema = 'Schema';

  /// Presentation copy for the English originals kept in `about.json`'s
  /// `status` block. The document is never displayed verbatim, so translating
  /// the UI later does not touch the data.
  static const Map<String, String> statusTexts = {
    'forecasts':
        'Raw ensemble members: not bias-corrected, not calibrated, and not quality-controlled '
        'beyond the source quality flag.',
    'verification':
        'No verification results (CRPS, CRPSS, Brier, reliability, coverage, leaderboard) are '
        'published before the 15-issue-date gate in docs/EVALUATION_PROTOCOL.md.',
    'observations':
        'The SMN regtemp snapshot is archived as served; gaps stay null and are never filled. '
        'The 2026-11-14 product precedence rule applies (regtemp primary).',
  };

  static const Map<String, String> modelLabels = {
    'ecmwf_ifs025': 'ECMWF IFS',
    'gfs_seamless': 'GFS',
  };

  static String modelLabel(String id) => modelLabels[id] ?? id;

  static String stationCount(int count) =>
      count == 1 ? '1 station' : '$count stations';

  static String leadDay(int lead) => '+$lead d';

  static String missingMembers(int members, int nominal) =>
      'no data ($members/$nominal members)';

  static String errorTitle(String document) => 'Could not read $document';

  static String schemaUnsupported(String version) =>
      'Schema version "$version" is not supported by this app '
      '(expected 1.0). Update the app or the export.';

  static String parseError(String document, String detail) =>
      'Document $document is not in the expected format: $detail';

  static String networkError(String document, String detail) =>
      'Could not download $document: $detail';

  static String httpError(String document, int status) =>
      'The data source returned HTTP $status for $document.';

  static String attributionLicence(String licence) => licence;

  static String datasetLinkLabel(String url) => url;
}
