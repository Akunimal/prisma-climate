import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:prisma_app/src/data/models.dart';

String fixture(String name) => File('test/fixtures/$name').readAsStringSync();

void main() {
  group('latest.json', () {
    late LatestDocument latest;

    setUpAll(() {
      latest = LatestDocument.parse(fixture('latest.json'));
    });

    test('parses the schema version, issue metadata and models', () {
      expect(latest.schemaVersion, supportedSchemaVersion);
      expect(latest.issueDate, '2026-11-14');
      expect(latest.issueTime, '2026-11-14T00:16:46Z');
      expect(latest.models, ['ecmwf_ifs025', 'gfs_seamless']);
      expect(latest.generatedAt, endsWith('Z'));
    });

    test('keeps the station fields the list screen needs', () {
      expect(latest.stations, hasLength(2));
      final station = latest.stationById('la_quiaca')!;
      expect(station.name, 'La Quiaca Observatorio');
      expect(station.climateZone, isNotEmpty);
      expect(station.lat, closeTo(-22.1, 1e-9));
      expect(station.lon, closeTo(-65.6, 1e-9));
      expect(latest.stationById('missing'), isNull);
    });
  });

  group('stations/<id>.json', () {
    late StationDocument laQuiaca;

    setUpAll(() {
      laQuiaca = StationDocument.parse(
        fixture('stations/la_quiaca.json'),
        document: 'stations/la_quiaca.json',
      );
    });

    test('parses the 16 lead days and both models', () {
      expect(laQuiaca.leadDays, hasLength(16));
      expect(laQuiaca.leadDays.first, 0);
      expect(laQuiaca.leadDays.last, 15);
      expect(laQuiaca.casesFor('t2m_max', 'ecmwf_ifs025'), hasLength(16));
      expect(laQuiaca.casesFor('t2m_max', 'gfs_seamless'), hasLength(16));
      expect(laQuiaca.casesFor('precip', 'gfs_seamless').first.fractionGe1mm, isNotNull);
    });

    test('parses an ok case with its bands and percentiles', () {
      final item = laQuiaca.caseAt('t2m_max', 'gfs_seamless', 0)!;
      expect(item.isMissing, isFalse);
      expect(item.nMembers, 31);
      expect(item.nominalMembers, 31);
      expect(item.p10, lessThanOrEqualTo(item.p25!));
      expect(item.p25, lessThanOrEqualTo(item.p50!));
      expect(item.p50, lessThanOrEqualTo(item.p75!));
      expect(item.p75, lessThanOrEqualTo(item.p90!));
      expect(item.min, lessThanOrEqualTo(item.p10!));
      expect(item.max, greaterThanOrEqualTo(item.p90!));
    });

    test('parses a missing_members case without inventing values', () {
      final item = laQuiaca.caseAt('t2m_max', 'ecmwf_ifs025', 15)!;
      expect(item.status, 'missing_members');
      expect(item.isMissing, isTrue);
      expect(item.nMembers, 0);
      expect(item.nominalMembers, 51);
      expect(item.p10, isNull);
      expect(item.p50, isNull);
      expect(item.p90, isNull);
      expect(item.min, isNull);
      expect(item.max, isNull);
    });

    test('keeps observations and their nulls as null', () {
      expect(laQuiaca.observed, hasLength(30));
      expect(laQuiaca.observed.first.date, matches(RegExp(r'^\d{4}-\d{2}-\d{2}$')));
      for (final day in laQuiaca.observed) {
        expect(day.t2mMax != null || day.t2mMin != null, isTrue);
      }
    });

    test('never exports a skill-metric field', () {
      final text = fixture('stations/la_quiaca.json').toLowerCase();
      for (final metric in const [
        'crps',
        'crpss',
        'brier',
        'reliability',
        'leaderboard',
        'coverage',
      ]) {
        expect(text.contains('"$metric"'), isFalse, reason: metric);
      }
    });
  });

  group('skill.json', () {
    late SkillDocument skill;

    setUpAll(() {
      skill = SkillDocument.parse(fixture('skill.json'));
    });

    test('parses the hindcast label, means and closed gate', () {
      expect(skill.schemaVersion, supportedSchemaVersion);
      expect(skill.label, 'hindcast');
      expect(skill.available, isTrue);
      expect(skill.provider, 'gfs');
      expect(skill.meanCrpssEmos, closeTo(-0.0774, 1e-9));
      expect(skill.meanCrpssQm, closeTo(0.0002, 1e-9));
      expect(skill.nCells, 19);
      expect(skill.nSufficient, 19);
      expect(skill.gate.open, isFalse);
      expect(skill.gate.operationalLeaderboardPublished, isFalse);
      expect(skill.gate.requiredIssueDates, 15);
      expect(skill.cells, hasLength(3));
      expect(skill.cells.first.station, 'buenos_aires');
      expect(skill.cells.first.insufficient, isFalse);
    });

    test('parses an unavailable document without means', () {
      final empty = SkillDocument.parse(
        '{"schema_version":"1.0","label":"hindcast","available":false,'
        '"gate":{"required_issue_dates":15,"archived_issue_dates":0,'
        '"open":false,"operational_leaderboard_published":false,'
        '"note":"gate"},"message":"none"}',
      );
      expect(empty.available, isFalse);
      expect(empty.meanCrpssEmos, isNull);
      expect(empty.message, 'none');
      expect(empty.gate.operationalLeaderboardPublished, isFalse);
    });
  });

  group('about.json', () {
    late AboutDocument about;

    setUpAll(() {
      about = AboutDocument.parse(fixture('about.json'));
    });

    test('parses the sources, licences and attribution links', () {
      expect(about.schemaVersion, supportedSchemaVersion);
      expect(about.sources, hasLength(2));
      final openMeteo = about.sources.firstWhere((source) => source.id == 'openmeteo-ensemble');
      expect(openMeteo.attribution, 'Weather data by Open-Meteo.com');
      expect(openMeteo.licence, 'CC BY 4.0');
      expect(openMeteo.attributionUrl, startsWith('https://'));
      final smn = about.sources.firstWhere((source) => source.id == 'smn-argentina');
      expect(smn.licence, 'CC BY 2.5 AR');
      expect(smn.licenceUrl, contains('creativecommons.org'));
    });

    test('has a UI text for every status field in the document', () {
      expect(about.status.keys.toSet(), aboutStatusKeys.toSet());
      expect(about.smnSnapshotDate, '2026-11-12');
      expect(about.region.timezone, 'America/Argentina/Cordoba');
    });
  });

  group('places', () {
    late PlaceIndex index;
    late PlaceDocument document;

    setUpAll(() {
      index = PlaceIndex.parse(fixture('places/index.json'));
      document = PlaceDocument.parse(
        fixture('places/ar.json'),
        document: 'places/ar.json',
      );
    });

    test('parses the registry and finds the region file', () {
      expect(index.schemaVersion, supportedSchemaVersion);
      final region = index.regionById('argentina');
      expect(region, isNotNull);
      expect(region!.file, 'ar.json');
      expect(region.country, 'AR');
      expect(region.source, 'geonames');
      expect(region.placeCount, 7);
      expect(index.regionById('missing'), isNull);
    });

    test('parses places with their attribution and licence', () {
      expect(document.schemaVersion, supportedSchemaVersion);
      expect(document.country, 'AR');
      expect(document.attribution, 'Place data from GeoNames');
      expect(document.attributionUrl, 'https://www.geonames.org/');
      expect(document.licence, 'CC BY 4.0');
      expect(document.licenceUrl, contains('creativecommons.org'));
      expect(document.places, hasLength(7));
      final cordoba = document.places.firstWhere((place) => place.name == 'Córdoba');
      expect(cordoba.admin1, 'Cordoba');
      expect(cordoba.lat, closeTo(-31.4065, 1e-9));
      expect(cordoba.lon, closeTo(-64.1885, 1e-9));
      expect(cordoba.population, 2106734);
    });

    test('rejects a place without a schema version', () {
      expect(
        () => PlaceDocument.parse('{"places": []}'),
        throwsA(isA<DataException>()),
      );
    });
  });

  group('rejections', () {
    test('rejects an unknown schema_version with the version and document', () {
      final body = fixture('latest.json').replaceFirst('"1.0"', '"2.0"');
      expect(
        () => LatestDocument.parse(body, document: 'latest.json'),
        throwsA(
          isA<SchemaVersionException>()
              .having((error) => error.found, 'found', '2.0')
              .having((error) => error.document, 'document', 'latest.json'),
        ),
      );
    });

    test('rejects malformed JSON with the English message and the document', () {
      expect(
        () => LatestDocument.parse('{not json', document: 'latest.json'),
        throwsA(
          isA<DataException>().having(
            (error) => error.message,
            'message',
            allOf(
              startsWith('Invalid JSON in latest.json: '),
              isNot(contains('inválido')),
            ),
          ),
        ),
      );
    });

    test('rejects a non-text models entry with the English message', () {
      final body = fixture('latest.json').replaceFirst(
        '"ecmwf_ifs025"',
        '42',
      );
      expect(
        () => LatestDocument.parse(body, document: 'latest.json'),
        throwsA(
          isA<DataException>().having(
            (error) => error.message,
            'message',
            'The "models" field contains a non-text value.',
          ),
        ),
      );
    });

    test('rejects a document without schema_version', () {
      expect(
        () => AboutDocument.parse('{"generated_at": "2026-11-14T00:00:00Z"}'),
        throwsA(isA<DataException>()),
      );
    });
  });
}
