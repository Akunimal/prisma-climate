import 'dart:convert';

const String supportedSchemaVersion = '1.0';

/// Keys of `about.json`'s `status` block that the app shows as presentation
/// copy. `smn_snapshot_date` is data, not copy, and is parsed separately.
const List<String> aboutStatusKeys = <String>[
  'forecasts',
  'verification',
  'observations',
];

/// How a [DataException] should be worded in the UI. The English [DataException.message]
/// is kept for logs and tests; `describeError` picks the localised sentence.
enum DataErrorKind {
  network,
  http,
  parse,
  invalidJson,
  modelsNonText,
  schema,
  fieldNotObject,
  fieldNotArray,
  missingText,
  missingInteger,
  notNumeric,
  missingSchema,
}

class DataException implements Exception {
  const DataException(
    this.message, {
    required this.kind,
    this.document,
    this.detail,
    this.status,
    this.field,
  });

  /// English sentence; used for logs, tests and unknown kinds.
  final String message;
  final DataErrorKind kind;
  final String? document;
  final String? detail;
  final int? status;
  final String? field;

  @override
  String toString() => message;
}

class SchemaVersionException extends DataException {
  SchemaVersionException({required this.found, required String document})
      : super(
          'unsupported schema_version',
          kind: DataErrorKind.schema,
          document: document,
          detail: found,
        );

  final String found;
}

Map<String, dynamic> _map(Object? value, String field) {
  if (value is Map<String, dynamic>) {
    return value;
  }
  throw DataException(
    'Field "$field" is not a JSON object.',
    kind: DataErrorKind.fieldNotObject,
    field: field,
  );
}

List<dynamic> _list(Object? value, String field) {
  if (value is List<dynamic>) {
    return value;
  }
  throw DataException(
    'Field "$field" is not a JSON array.',
    kind: DataErrorKind.fieldNotArray,
    field: field,
  );
}

String _string(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is String) {
    return value;
  }
  throw DataException(
    'Missing text field "$field" or it is not a string.',
    kind: DataErrorKind.missingText,
    field: field,
  );
}

int _integer(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is int) {
    return value;
  }
  if (value is num) {
    return value.toInt();
  }
  throw DataException(
    'Missing integer "$field" or it is not a number.',
    kind: DataErrorKind.missingInteger,
    field: field,
  );
}

double? _doubleOrNull(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value == null) {
    return null;
  }
  if (value is num) {
    return value.toDouble();
  }
  throw DataException(
    'Field "$field" is not numeric.',
    kind: DataErrorKind.notNumeric,
    field: field,
  );
}

void _checkSchema(Map<String, dynamic> json, String document) {
  final version = json['schema_version'];
  if (version is! String) {
    throw DataException(
      'Missing schema_version field in $document.',
      kind: DataErrorKind.missingSchema,
      document: document,
    );
  }
  if (version != supportedSchemaVersion) {
    throw SchemaVersionException(found: version, document: document);
  }
}

class StationSummary {
  const StationSummary({
    required this.id,
    required this.name,
    required this.lat,
    required this.lon,
    required this.climateZone,
  });

  factory StationSummary.fromJson(Object? value) {
    final json = _map(value, 'station');
    return StationSummary(
      id: _string(json, 'id'),
      name: _string(json, 'name'),
      lat: _doubleOrNull(json, 'lat') ?? 0,
      lon: _doubleOrNull(json, 'lon') ?? 0,
      climateZone: _string(json, 'climate_zone'),
    );
  }

  final String id;
  final String name;
  final double lat;
  final double lon;
  final String climateZone;
}

class PlaceRecord {
  const PlaceRecord({
    required this.name,
    required this.admin1,
    required this.lat,
    required this.lon,
    required this.population,
  });

  factory PlaceRecord.fromJson(Object? value) {
    final json = _map(value, 'place');
    return PlaceRecord(
      name: _string(json, 'name'),
      admin1: _string(json, 'admin1'),
      lat: _doubleOrNull(json, 'lat') ?? 0,
      lon: _doubleOrNull(json, 'lon') ?? 0,
      population: _integer(json, 'population'),
    );
  }

  final String name;
  final String admin1;
  final double lat;
  final double lon;
  final int population;
}

class PlaceRegion {
  const PlaceRegion({
    required this.file,
    required this.country,
    required this.source,
    required this.placeCount,
  });

  factory PlaceRegion.fromJson(Object? value) {
    final json = _map(value, 'place region');
    return PlaceRegion(
      file: _string(json, 'file'),
      country: _string(json, 'country'),
      source: _string(json, 'source'),
      placeCount: _integer(json, 'place_count'),
    );
  }

  final String file;
  final String country;
  final String source;
  final int placeCount;
}

class PlaceIndex {
  const PlaceIndex({required this.schemaVersion, required this.regions});

  factory PlaceIndex.parse(String body, {String document = 'places/index.json'}) {
    final Object? decoded;
    try {
      decoded = jsonDecode(body);
    } on FormatException catch (error) {
      throw DataException(
        'Invalid JSON in $document: ${error.message}',
        kind: DataErrorKind.invalidJson,
        document: document,
        detail: error.message,
      );
    }
    final json = _map(decoded, document);
    _checkSchema(json, document);
    final regions = <String, PlaceRegion>{};
    _map(json['regions'], 'regions').forEach((regionId, value) {
      regions[regionId] = PlaceRegion.fromJson(value);
    });
    return PlaceIndex(
      schemaVersion: _string(json, 'schema_version'),
      regions: regions,
    );
  }

  final String schemaVersion;
  final Map<String, PlaceRegion> regions;

  PlaceRegion? regionById(String id) => regions[id];
}

class PlaceDocument {
  const PlaceDocument({
    required this.schemaVersion,
    required this.country,
    required this.source,
    required this.attribution,
    required this.attributionUrl,
    required this.licence,
    required this.licenceUrl,
    required this.places,
  });

  factory PlaceDocument.parse(String body, {String document = 'places/ar.json'}) {
    final Object? decoded;
    try {
      decoded = jsonDecode(body);
    } on FormatException catch (error) {
      throw DataException(
        'Invalid JSON in $document: ${error.message}',
        kind: DataErrorKind.invalidJson,
        document: document,
        detail: error.message,
      );
    }
    final json = _map(decoded, document);
    _checkSchema(json, document);
    return PlaceDocument(
      schemaVersion: _string(json, 'schema_version'),
      country: _string(json, 'country'),
      source: _string(json, 'source'),
      attribution: _string(json, 'attribution'),
      attributionUrl: _string(json, 'attribution_url'),
      licence: _string(json, 'licence'),
      licenceUrl: _string(json, 'licence_url'),
      places: _list(json['places'], 'places')
          .map((value) => PlaceRecord.fromJson(value))
          .toList(),
    );
  }

  final String schemaVersion;
  final String country;
  final String source;
  final String attribution;
  final String attributionUrl;
  final String licence;
  final String licenceUrl;
  final List<PlaceRecord> places;
}

class LatestDocument {
  const LatestDocument({
    required this.schemaVersion,
    required this.generatedAt,
    required this.issueDate,
    required this.issueTime,
    required this.models,
    required this.stations,
  });

  factory LatestDocument.parse(String body, {String document = 'latest.json'}) {
    final Object? decoded;
    try {
      decoded = jsonDecode(body);
    } on FormatException catch (error) {
      throw DataException(
        'Invalid JSON in $document: ${error.message}',
        kind: DataErrorKind.invalidJson,
        document: document,
        detail: error.message,
      );
    }
    final json = _map(decoded, document);
    _checkSchema(json, document);
    return LatestDocument(
      schemaVersion: _string(json, 'schema_version'),
      generatedAt: _string(json, 'generated_at'),
      issueDate: _string(json, 'issue_date'),
      issueTime: _string(json, 'issue_time'),
      models: _list(json['models'], 'models').map((model) {
        if (model is String) {
          return model;
        }
        throw const DataException(
          'The "models" field contains a non-text value.',
          kind: DataErrorKind.modelsNonText,
        );
      }).toList(),
      stations: _list(json['stations'], 'stations')
          .map((station) => StationSummary.fromJson(station))
          .toList(),
    );
  }

  final String schemaVersion;
  final String generatedAt;
  final String issueDate;
  final String issueTime;
  final List<String> models;
  final List<StationSummary> stations;

  StationSummary? stationById(String id) {
    for (final station in stations) {
      if (station.id == id) {
        return station;
      }
    }
    return null;
  }
}

class ForecastCase {
  const ForecastCase({
    required this.leadDay,
    required this.validLocalDate,
    required this.nMembers,
    required this.nominalMembers,
    required this.status,
    required this.p10,
    required this.p25,
    required this.p50,
    required this.p75,
    required this.p90,
    required this.min,
    required this.max,
    required this.fractionGe1mm,
    required this.fractionGe10mm,
  });

  factory ForecastCase.fromJson(Object? value) {
    final json = _map(value, 'forecast case');
    return ForecastCase(
      leadDay: _integer(json, 'lead_day'),
      validLocalDate: _string(json, 'valid_local_date'),
      nMembers: _integer(json, 'n_members'),
      nominalMembers: _integer(json, 'nominal_members'),
      status: _string(json, 'status'),
      p10: _doubleOrNull(json, 'p10'),
      p25: _doubleOrNull(json, 'p25'),
      p50: _doubleOrNull(json, 'p50'),
      p75: _doubleOrNull(json, 'p75'),
      p90: _doubleOrNull(json, 'p90'),
      min: _doubleOrNull(json, 'min'),
      max: _doubleOrNull(json, 'max'),
      fractionGe1mm: _doubleOrNull(json, 'fraction_ge_1mm'),
      fractionGe10mm: _doubleOrNull(json, 'fraction_ge_10mm'),
    );
  }

  final int leadDay;
  final String validLocalDate;
  final int nMembers;
  final int nominalMembers;
  final String status;
  final double? p10;
  final double? p25;
  final double? p50;
  final double? p75;
  final double? p90;
  final double? min;
  final double? max;
  final double? fractionGe1mm;
  final double? fractionGe10mm;

  bool get isMissing => status != 'ok';
}

class ObservedDay {
  const ObservedDay({required this.date, required this.t2mMax, required this.t2mMin});

  factory ObservedDay.fromJson(Object? value) {
    final json = _map(value, 'observed day');
    return ObservedDay(
      date: _string(json, 'date'),
      t2mMax: _doubleOrNull(json, 't2m_max'),
      t2mMin: _doubleOrNull(json, 't2m_min'),
    );
  }

  final String date;
  final double? t2mMax;
  final double? t2mMin;
}

class StationDocument {
  const StationDocument({
    required this.schemaVersion,
    required this.generatedAt,
    required this.issueDate,
    required this.issueTime,
    required this.models,
    required this.station,
    required this.forecast,
    required this.observed,
  });

  factory StationDocument.parse(String body, {String document = 'station.json'}) {
    final Object? decoded;
    try {
      decoded = jsonDecode(body);
    } on FormatException catch (error) {
      throw DataException(
        'Invalid JSON in $document: ${error.message}',
        kind: DataErrorKind.invalidJson,
        document: document,
        detail: error.message,
      );
    }
    final json = _map(decoded, document);
    _checkSchema(json, document);

    final forecast = <String, Map<String, List<ForecastCase>>>{};
    _map(json['forecast'], 'forecast').forEach((variable, modelsValue) {
      final models = <String, List<ForecastCase>>{};
      _map(modelsValue, 'forecast.$variable').forEach((model, casesValue) {
        models[model] = _list(casesValue, 'forecast.$variable.$model')
            .map((value) => ForecastCase.fromJson(value))
            .toList();
      });
      forecast[variable] = models;
    });

    return StationDocument(
      schemaVersion: _string(json, 'schema_version'),
      generatedAt: _string(json, 'generated_at'),
      issueDate: _string(json, 'issue_date'),
      issueTime: _string(json, 'issue_time'),
      models: _list(json['models'], 'models').map((model) {
        if (model is String) {
          return model;
        }
        throw const DataException(
          'The "models" field contains a non-text value.',
          kind: DataErrorKind.modelsNonText,
        );
      }).toList(),
      station: StationSummary.fromJson(json['station']),
      forecast: forecast,
      observed: _list(json['observed'], 'observed')
          .map((value) => ObservedDay.fromJson(value))
          .toList(),
    );
  }

  final String schemaVersion;
  final String generatedAt;
  final String issueDate;
  final String issueTime;
  final List<String> models;
  final StationSummary station;
  final Map<String, Map<String, List<ForecastCase>>> forecast;
  final List<ObservedDay> observed;

  List<ForecastCase> casesFor(String variable, String model) =>
      forecast[variable]?[model] ?? const <ForecastCase>[];

  List<ForecastCase> get temperatureCases =>
      casesFor('t2m_max', models.isEmpty ? '' : models.first);

  ForecastCase? caseAt(String variable, String model, int leadDay) {
    for (final item in casesFor(variable, model)) {
      if (item.leadDay == leadDay) {
        return item;
      }
    }
    return null;
  }

  List<int> get leadDays {
    final days = <int>{};
    for (final models in forecast.values) {
      for (final cases in models.values) {
        for (final item in cases) {
          days.add(item.leadDay);
        }
      }
    }
    final sorted = days.toList()..sort();
    return sorted;
  }
}

class AboutSource {
  const AboutSource({
    required this.id,
    required this.name,
    required this.role,
    required this.licence,
    required this.licenceUrl,
    required this.attribution,
    required this.attributionUrl,
  });

  factory AboutSource.fromJson(Object? value) {
    final json = _map(value, 'source');
    return AboutSource(
      id: _string(json, 'id'),
      name: _string(json, 'name'),
      role: _string(json, 'role'),
      licence: _string(json, 'licence'),
      licenceUrl: _string(json, 'licence_url'),
      attribution: _string(json, 'attribution'),
      attributionUrl: _string(json, 'attribution_url'),
    );
  }

  final String id;
  final String name;
  final String role;
  final String licence;
  final String licenceUrl;
  final String attribution;
  final String attributionUrl;
}

class RegionInfo {
  const RegionInfo({required this.id, required this.name, required this.timezone});

  factory RegionInfo.fromJson(Object? value) {
    final json = _map(value, 'region');
    return RegionInfo(
      id: _string(json, 'id'),
      name: _string(json, 'name'),
      timezone: _string(json, 'timezone'),
    );
  }

  final String id;
  final String name;
  final String timezone;
}

class AboutDocument {
  const AboutDocument({
    required this.schemaVersion,
    required this.generatedAt,
    required this.datasetUrl,
    required this.region,
    required this.sources,
    required this.status,
    required this.smnSnapshotDate,
  });

  factory AboutDocument.parse(String body, {String document = 'about.json'}) {
    final Object? decoded;
    try {
      decoded = jsonDecode(body);
    } on FormatException catch (error) {
      throw DataException(
        'Invalid JSON in $document: ${error.message}',
        kind: DataErrorKind.invalidJson,
        document: document,
        detail: error.message,
      );
    }
    final json = _map(decoded, document);
    _checkSchema(json, document);

    final status = <String, String>{};
    String? smnSnapshotDate;
    _map(json['status'], 'status').forEach((key, value) {
      if (value is! String) {
        return;
      }
      if (key == 'smn_snapshot_date') {
        smnSnapshotDate = value;
      } else {
        status[key] = value;
      }
    });

    return AboutDocument(
      schemaVersion: _string(json, 'schema_version'),
      generatedAt: _string(json, 'generated_at'),
      datasetUrl: _string(json, 'dataset_url'),
      region: RegionInfo.fromJson(json['region']),
      sources: _list(json['sources'], 'sources')
          .map((value) => AboutSource.fromJson(value))
          .toList(),
      status: status,
      smnSnapshotDate: smnSnapshotDate,
    );
  }

  final String schemaVersion;
  final String generatedAt;
  final String datasetUrl;
  final RegionInfo region;
  final List<AboutSource> sources;
  final Map<String, String> status;
  final String? smnSnapshotDate;
}

class SkillGate {
  const SkillGate({
    required this.requiredIssueDates,
    required this.archivedIssueDates,
    required this.open,
    required this.operationalLeaderboardPublished,
    required this.note,
  });

  factory SkillGate.fromJson(Object? value) {
    final json = _map(value, 'gate');
    return SkillGate(
      requiredIssueDates: _integer(json, 'required_issue_dates'),
      archivedIssueDates: _integer(json, 'archived_issue_dates'),
      open: json['open'] == true,
      operationalLeaderboardPublished:
          json['operational_leaderboard_published'] == true,
      note: _string(json, 'note'),
    );
  }

  final int requiredIssueDates;
  final int archivedIssueDates;
  final bool open;
  final bool operationalLeaderboardPublished;
  final String note;
}

/// Hindcast-labelled calibration scores from `skill.json`.
///
/// Operational leaderboard numbers are never present: `gate`
/// always reports `operationalLeaderboardPublished == false` until the
/// 15-issue-date gate opens.
class SkillDocument {
  const SkillDocument({
    required this.schemaVersion,
    required this.label,
    required this.available,
    required this.gate,
    this.message,
    this.provider,
    this.retrievedAt,
    this.mode,
    this.windowStart,
    this.windowEnd,
    this.leads,
    this.nCells,
    this.nSufficient,
    this.meanCrpssEmos,
    this.meanCrpssQm,
    this.note,
    this.cells = const [],
  });

  factory SkillDocument.parse(String body, {String document = 'skill.json'}) {
    final Object? decoded;
    try {
      decoded = jsonDecode(body);
    } on FormatException catch (error) {
      throw DataException(
        'Invalid JSON in $document: ${error.message}',
        kind: DataErrorKind.invalidJson,
        document: document,
        detail: error.message,
      );
    }
    final json = _map(decoded, document);
    _checkSchema(json, document);

    final window = json['window'];
    String? windowStart;
    String? windowEnd;
    if (window is Map<String, dynamic>) {
      windowStart = window['start'] is String ? window['start'] as String : null;
      windowEnd = window['end'] is String ? window['end'] as String : null;
    }

    final cells = <SkillCell>[
      if (json['cells'] is List)
        for (final value in json['cells'] as List<dynamic>)
          SkillCell.fromJson(value),
    ];

    return SkillDocument(
      schemaVersion: _string(json, 'schema_version'),
      label: json['label'] is String ? json['label'] as String : 'hindcast',
      available: json['available'] == true,
      gate: SkillGate.fromJson(json['gate']),
      message: json['message'] is String ? json['message'] as String : null,
      provider: json['provider'] is String ? json['provider'] as String : null,
      retrievedAt:
          json['retrieved_at'] is String ? json['retrieved_at'] as String : null,
      mode: json['mode'] is String ? json['mode'] as String : null,
      windowStart: windowStart,
      windowEnd: windowEnd,
      leads: json['leads'] is List
          ? (json['leads'] as List<dynamic>)
              .whereType<num>()
              .map((value) => value.toInt())
              .toList()
          : null,
      nCells: json['n_cells'] is num ? (json['n_cells'] as num).toInt() : null,
      nSufficient:
          json['n_sufficient'] is num ? (json['n_sufficient'] as num).toInt() : null,
      meanCrpssEmos: _doubleOrNull(json, 'mean_crpss_emos_vs_raw'),
      meanCrpssQm: _doubleOrNull(json, 'mean_crpss_qm_vs_raw'),
      note: json['note'] is String ? json['note'] as String : null,
      cells: cells,
    );
  }

  final String schemaVersion;
  final String label;
  final bool available;
  final SkillGate gate;
  final String? message;
  final String? provider;
  final String? retrievedAt;
  final String? mode;
  final String? windowStart;
  final String? windowEnd;
  final List<int>? leads;
  final int? nCells;
  final int? nSufficient;
  final double? meanCrpssEmos;
  final double? meanCrpssQm;
  final String? note;
  final List<SkillCell> cells;
}

class SkillCell {
  const SkillCell({
    required this.station,
    required this.leadDay,
    required this.insufficient,
    this.crpssEmos,
    this.crpssQm,
  });

  factory SkillCell.fromJson(Object? value) {
    final json = _map(value, 'skill cell');
    return SkillCell(
      station: json['station'] is String ? json['station'] as String : '',
      leadDay: json['lead_day'] is num ? (json['lead_day'] as num).toInt() : 0,
      insufficient: json['insufficient'] == true,
      crpssEmos: _doubleOrNull(json, 'crpss_emos_vs_raw'),
      crpssQm: _doubleOrNull(json, 'crpss_qm_vs_raw'),
    );
  }

  final String station;
  final int leadDay;
  final bool insufficient;
  final double? crpssEmos;
  final double? crpssQm;
}
