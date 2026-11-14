import 'dart:convert';

const String supportedSchemaVersion = '1.0';

class DataException implements Exception {
  const DataException(this.message);

  final String message;

  @override
  String toString() => message;
}

class SchemaVersionException extends DataException {
  SchemaVersionException({required this.found, required this.document})
      : super('unsupported schema_version');

  final String found;
  final String document;
}

Map<String, dynamic> _map(Object? value, String field) {
  if (value is Map<String, dynamic>) {
    return value;
  }
  throw DataException('Field "$field" is not a JSON object.');
}

List<dynamic> _list(Object? value, String field) {
  if (value is List<dynamic>) {
    return value;
  }
  throw DataException('Field "$field" is not a JSON array.');
}

String _string(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is String) {
    return value;
  }
  throw DataException('Missing text field "$field" or it is not a string.');
}

int _integer(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is int) {
    return value;
  }
  if (value is num) {
    return value.toInt();
  }
  throw DataException('Missing integer "$field" or it is not a number.');
}

double? _doubleOrNull(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value == null) {
    return null;
  }
  if (value is num) {
    return value.toDouble();
  }
  throw DataException('Field "$field" is not numeric.');
}

void _checkSchema(Map<String, dynamic> json, String document) {
  final version = json['schema_version'];
  if (version is! String) {
    throw DataException('Missing schema_version field in $document.');
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
      throw DataException('Invalid JSON in $document: ${error.message}');
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
        throw const DataException('The "models" field contains a non-text value.');
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
      throw DataException('Invalid JSON in $document: ${error.message}');
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
        throw const DataException('The "models" field contains a non-text value.');
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
      throw DataException('Invalid JSON in $document: ${error.message}');
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
