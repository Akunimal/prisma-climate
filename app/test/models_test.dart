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

    test('parses optional t2m_max and t2m_min when present, defaults to null', () {
      final summaryWithTemps = StationSummary.fromJson({
        'id': 'test_station',
        'name': 'Test Station',
        'lat': -34.0,
        'lon': -58.0,
        'climate_zone': 'Pampa',
        't2m_max': 28.5,
        't2m_min': 15.2,
      });
      expect(summaryWithTemps.t2mMax, 28.5);
      expect(summaryWithTemps.t2mMin, 15.2);

      final summaryNoTemps = StationSummary.fromJson({
        'id': 'test_station',
        'name': 'Test Station',
        'lat': -34.0,
        'lon': -58.0,
        'climate_zone': 'Pampa',
      });
      expect(summaryNoTemps.t2mMax, isNull);
      expect(summaryNoTemps.t2mMin, isNull);
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

  group('leaderboard.json', () {
    late LeaderboardDocument leaderboard;

    setUpAll(() {
      leaderboard = LeaderboardDocument.parse(fixture('leaderboard.json'));
    });

    test('parses locked state with honest progress metadata', () {
      expect(leaderboard.schemaVersion, supportedSchemaVersion);
      expect(leaderboard.protocol, 'docs/EVALUATION_PROTOCOL.md');
      expect(leaderboard.gate.status, 'locked');
      expect(leaderboard.gate.isLocked, isTrue);
      expect(leaderboard.gate.isUnlocked, isFalse);
      expect(leaderboard.gate.open, isFalse);
      expect(leaderboard.gate.archivedIssueDates, 13);
      expect(leaderboard.gate.requiredIssueDates, 15);
      expect(leaderboard.gate.remainingIssueDates, 2);
      expect(leaderboard.summary, isNull);
      expect(leaderboard.cells, isEmpty);
    });

    test('parses unlocked state with summary and cells', () {
      const synthetic = '''
      {
        "schema_version": "1.0",
        "generated_at": "2026-11-23T18:00:00Z",
        "protocol": "docs/EVALUATION_PROTOCOL.md",
        "gate": {
          "status": "unlocked",
          "required_issue_dates": 15,
          "archived_issue_dates": 15,
          "remaining_issue_dates": 0,
          "open": true,
          "operational_leaderboard_published": true,
          "note": "unlocked"
        },
        "summary": {
          "n_cells": 1,
          "n_sufficient": 1,
          "min_sample_threshold": 10,
          "mean_crpss_vs_climatology": 0.25,
          "mean_crpss_vs_persistence": 0.35
        },
        "models": ["gfs_seamless"],
        "baselines": ["climatology", "persistence"],
        "cells": [
          {
            "location": "cordoba",
            "variable": "t2m_max",
            "model": "gfs_seamless",
            "lead_day": 1,
            "n_pairs": 15,
            "n_missing": 0,
            "insufficient": false,
            "n_climatology": 15,
            "n_persistence": 15,
            "crps_raw": 1.5,
            "crps_climatology": 2.0,
            "crps_persistence": 2.2,
            "crpss_vs_climatology": 0.25,
            "crpss_vs_persistence": 0.35
          }
        ]
      }
      ''';
      final doc = LeaderboardDocument.parse(synthetic);
      expect(doc.gate.isUnlocked, isTrue);
      expect(doc.gate.isLocked, isFalse);
      expect(doc.summary, isNotNull);
      expect(doc.summary!.nCells, 1);
      expect(doc.summary!.meanCrpssVsClimatology, closeTo(0.25, 1e-9));
      expect(doc.summary!.meanCrpssVsPersistence, closeTo(0.35, 1e-9));
      expect(doc.cells, hasLength(1));
      expect(doc.cells.first.location, 'cordoba');
      expect(doc.cells.first.crpssVsClimatology, closeTo(0.25, 1e-9));
    });

    test('parses real unlocked drill payload from Python pipeline', () {
      final unlocked = LeaderboardDocument.parse(fixture('leaderboard_unlocked.json'));
      expect(unlocked.gate.status, 'unlocked');
      expect(unlocked.gate.isUnlocked, isTrue);
      expect(unlocked.gate.isLocked, isFalse);
      expect(unlocked.gate.open, isTrue);
      expect(unlocked.gate.operationalLeaderboardPublished, isTrue);
      expect(unlocked.gate.archivedIssueDates, 15);
      expect(unlocked.gate.remainingIssueDates, 0);

      expect(unlocked.summary, isNotNull);
      expect(unlocked.summary!.nCells, 3);
      expect(unlocked.summary!.nSufficient, 1);
      expect(unlocked.summary!.meanCrpssVsClimatology, closeTo(0.5, 1e-9));
      expect(unlocked.summary!.meanCrpssVsPersistence, closeTo(0.75, 1e-9));

      expect(unlocked.cells, hasLength(3));
      final gfs1 = unlocked.cells.firstWhere(
        (c) => c.model == 'gfs_seamless' && c.leadDay == 1,
      );
      expect(gfs1.location, 'Alfa');
      expect(gfs1.insufficient, isFalse);
      expect(gfs1.nPairs, 15);
      expect(gfs1.crpssVsClimatology, closeTo(0.5, 1e-9));
      expect(gfs1.crpssVsPersistence, closeTo(0.75, 1e-9));

      final gfs2 = unlocked.cells.firstWhere(
        (c) => c.model == 'gfs_seamless' && c.leadDay == 2,
      );
      expect(gfs2.insufficient, isTrue);
      expect(gfs2.crpssVsClimatology, isNull);

      final ecmwf = unlocked.cells.firstWhere(
        (c) => c.model == 'ecmwf_ifs025',
      );
      expect(ecmwf.insufficient, isTrue);
      expect(ecmwf.nMissing, 15);
      expect(ecmwf.crpsRaw, isNull);
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

  group('climatology', () {
    test('ClimatologyRange parses from JSON and serializes to JSON', () {
      final json = {'low': 15.5, 'high': 28.0, 'median': 21.2};
      final range = ClimatologyRange.fromJson(json);
      expect(range.low, 15.5);
      expect(range.high, 28.0);
      expect(range.median, 21.2);
      expect(range.toJson(), json);
    });

    test('StationDocument parses explicit climatology if present', () {
      final base = fixture('stations/buenos_aires.json');
      final withClim = base.replaceFirst(
        '"forecast": {',
        '"climatology": {"t2m_max": {"low": 14.0, "high": 27.5, "median": 20.0}}, "forecast": {',
      );
      final doc = StationDocument.parse(withClim);
      final clim = doc.climatologyFor('t2m_max');
      expect(clim, isNotNull);
      expect(clim!.low, 14.0);
      expect(clim.high, 27.5);
      expect(clim.median, 20.0);
    });

    test('StationDocument derives climatology range from observed history when absent', () {
      final doc = StationDocument.parse(fixture('stations/buenos_aires.json'));
      expect(doc.climatology, isNull);
      final derived = doc.climatologyFor('t2m_max');
      expect(derived, isNotNull);
      expect(derived!.low, lessThan(derived.high));
      expect(derived.median, isNotNull);
    });
  });
}
