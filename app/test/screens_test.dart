import 'dart:convert';
import 'dart:io';

import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:material_ui/material_ui.dart';
import 'package:prisma_app/l10n/generated/app_localizations_en.dart';
import 'package:prisma_app/src/app.dart';
import 'package:prisma_app/src/data/models.dart';
import 'package:prisma_app/src/data/repository.dart';
import 'package:prisma_app/src/location_provider.dart';
import 'package:prisma_app/src/map_tiles.dart';
import 'package:prisma_app/src/nearest_station.dart';
import 'package:prisma_app/src/widgets/band_chart.dart';
import 'package:shared_preferences/shared_preferences.dart';

String fixture(String name) => File('test/fixtures/$name').readAsStringSync();

/// English strings as the running app renders them under the default locale.
final AppLocalizationsEn en = AppLocalizationsEn();

Map<String, String> defaultFiles() => {
      'latest.json': fixture('latest.json'),
      'about.json': fixture('about.json'),
      'skill.json': fixture('skill.json'),
      'leaderboard.json': fixture('leaderboard.json'),
      'stations/la_quiaca.json': fixture('stations/la_quiaca.json'),
      'stations/buenos_aires.json': fixture('stations/buenos_aires.json'),
      'places/index.json': fixture('places/index.json'),
      'places/ar.json': fixture('places/ar.json'),
    };

class FakeLocationProvider implements LocationProvider {
  FakeLocationProvider(this.handler);

  final Future<GeoPoint> Function() handler;

  @override
  Future<GeoPoint> currentPosition() => handler();
}

/// Serves a blank tile so map tests never touch the network.
class BlankTileProvider extends TileProvider {
  @override
  ImageProvider getImage(TileCoordinates coordinates, TileLayer options) =>
      MemoryImage(TileProvider.transparentImage);
}

http.Response ok(String body) => http.Response.bytes(
      utf8.encode(body),
      200,
      headers: const {'content-type': 'application/json; charset=utf-8'},
    );

http.Client mockClient(Map<String, String> files) {
  return MockClient((request) async {
    final path = request.url.path.replaceFirst('/data/', '');
    final body = files[path];
    if (body == null) {
      return http.Response('not found', 404);
    }
    return ok(body);
  });
}

Future<void> pumpApp(
  WidgetTester tester, {
  http.Client? client,
  Map<String, String>? files,
  Size size = const Size(1200, 900),
  LocationProvider? locationProvider,
  TileProvider? tileProvider,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final repository = PrismaRepository(
    client: client ?? mockClient(files ?? defaultFiles()),
    baseUrl: 'https://example.test/data/',
  );
  await tester.pumpWidget(
    PrismaApp(
      repository: repository,
      locationProvider: locationProvider,
      tileProvider: tileProvider,
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> openForecast(WidgetTester tester) async {
  await tester.tap(find.text(en.tabForecast));
  await tester.pumpAndSettle();
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets('Stations lists the stations with their climate zone', (tester) async {
    await pumpApp(tester);
    expect(find.text('2 stations'), findsOneWidget);
    expect(find.text('La Quiaca Observatorio'), findsOneWidget);
    expect(find.text('Buenos Aires Observatorio'), findsOneWidget);
    expect(find.textContaining('NOA / Puna'), findsOneWidget);
  });

  testWidgets('Stations search filters by name and by zone', (tester) async {
    await pumpApp(tester);
    await tester.enterText(find.byType(TextField), 'quia');
    await tester.pumpAndSettle();
    expect(find.text('La Quiaca Observatorio'), findsOneWidget);
    expect(find.text('Buenos Aires Observatorio'), findsNothing);

    await tester.enterText(find.byType(TextField), 'pampa');
    await tester.pumpAndSettle();
    expect(find.text('Buenos Aires Observatorio'), findsOneWidget);

    await tester.enterText(find.byType(TextField), 'zzz');
    await tester.pumpAndSettle();
    expect(find.text(en.searchNoResults), findsOneWidget);
  });

  testWidgets('Stations region filter chips filter stations list', (tester) async {
    await pumpApp(tester);
    expect(find.text('La Quiaca Observatorio'), findsOneWidget);

    // Filter to Europe: Americas fixture stations are hidden
    await tester.tap(find.text('Europe (18)'));
    await tester.pumpAndSettle();
    expect(find.text('La Quiaca Observatorio'), findsNothing);

    // Back to All: fixture stations return
    await tester.tap(find.text('All (140)'));
    await tester.pumpAndSettle();
    expect(find.text('La Quiaca Observatorio'), findsOneWidget);
  });

  testWidgets('place search groups stations and places', (tester) async {
    await pumpApp(tester);
    await tester.enterText(find.byType(TextField), 'buenos');
    await tester.pumpAndSettle();

    expect(find.text(en.searchStationsGroup), findsWidgets);
    expect(find.text(en.searchPlacesGroup), findsOneWidget);
    expect(find.text('Buenos Aires Observatorio'), findsOneWidget);
    expect(find.text('Buenos Aires'), findsOneWidget);
  });

  testWidgets('choosing a far place shows nearest station, distance and warning',
      (tester) async {
    await pumpApp(tester);
    await tester.enterText(find.byType(TextField), 'cordoba');
    await tester.pumpAndSettle();

    final placeTile = find.ancestor(
      of: find.byIcon(Icons.place_outlined),
      matching: find.byType(ListTile),
    );
    await tester.tap(placeTile.first);
    await tester.pumpAndSettle();

    expect(find.textContaining('Nearest station: Buenos Aires Observatorio'),
        findsOneWidget);
    expect(find.textContaining('Distance:'), findsOneWidget);
    expect(find.text(en.nearestStationWarning), findsOneWidget);
  });

  testWidgets('a place close to a station never shows the warning', (tester) async {
    await pumpApp(tester);
    await tester.enterText(find.byType(TextField), 'la quiaca');
    await tester.pumpAndSettle();

    final placeTile = find.ancestor(
      of: find.byIcon(Icons.place_outlined),
      matching: find.byType(ListTile),
    );
    await tester.tap(placeTile.first);
    await tester.pumpAndSettle();

    expect(find.textContaining('Nearest station: La Quiaca Observatorio'),
        findsOneWidget);
    expect(find.text(en.nearestStationWarning), findsNothing);
  });

  Future<void> openPlaceCard(WidgetTester tester, String query) async {
    await tester.enterText(find.byType(TextField), query);
    await tester.pumpAndSettle();
    final placeTile = find.ancestor(
      of: find.byIcon(Icons.place_outlined),
      matching: find.byType(ListTile),
    );
    await tester.tap(placeTile.first);
    await tester.pumpAndSettle();
  }

  Future<void> dismissNearestCard(WidgetTester tester) async {
    Navigator.of(tester.element(find.byType(AlertDialog))).pop();
    await tester.pumpAndSettle();
  }

  testWidgets('View forecast from a place card opens that station forecast',
      (tester) async {
    await pumpApp(tester);
    await openPlaceCard(tester, 'cordoba');

    await tester.tap(find.text(en.stationsViewForecast));
    await tester.pumpAndSettle();

    expect(find.text('Buenos Aires Observatorio'), findsOneWidget);
    expect(find.textContaining('Pampa ·'), findsOneWidget);
    expect(find.text(en.rawBanner), findsOneWidget);
  });

  testWidgets('the map shows the place marker, its link line and the stations',
      (tester) async {
    await pumpApp(tester, tileProvider: BlankTileProvider());
    await openPlaceCard(tester, 'cordoba');
    await dismissNearestCard(tester);

    await tester.tap(find.byTooltip(en.clearSearch));
    await tester.pumpAndSettle();
    await tester.tap(find.text(en.stationsViewMap));
    await tester.pumpAndSettle();

    expect(find.byType(PolylineLayer), findsOneWidget);
    expect(find.byIcon(Icons.place), findsOneWidget);
    expect(find.byTooltip('La Quiaca Observatorio'), findsOneWidget);
    expect(find.byTooltip('Buenos Aires Observatorio'), findsOneWidget);
  });

  testWidgets('the map shows temperature badges when t2mMax is present and toggles',
      (tester) async {
    final files = defaultFiles();
    final customLatest = jsonDecode(files['latest.json']!);
    customLatest['stations'][0]['t2m_max'] = 22.4;
    customLatest['stations'][0]['t2m_min'] = 11.2;
    files['latest.json'] = jsonEncode(customLatest);

    await pumpApp(tester, files: files, tileProvider: BlankTileProvider());
    await tester.tap(find.text(en.stationsViewMap));
    await tester.pumpAndSettle();

    // Map temp toggle button is present because station has t2m_max
    expect(find.byKey(const ValueKey('map_temp_toggle')), findsOneWidget);
    // Badge shows rounded temperature: 22°
    expect(find.text('22°'), findsOneWidget);

    // Tapping the toggle turns temperatures off (reverts to circles)
    await tester.tap(find.byKey(const ValueKey('map_temp_toggle')));
    await tester.pumpAndSettle();
    expect(find.text('22°'), findsNothing);

    // Tapping again restores temperature badges
    await tester.tap(find.byKey(const ValueKey('map_temp_toggle')));
    await tester.pumpAndSettle();
    expect(find.text('22°'), findsOneWidget);
  });

  testWidgets('the map toggles between OSM and NASA GIBS satellite layer',
      (tester) async {
    final files = defaultFiles();
    final customLatest = jsonDecode(files['latest.json']!);
    customLatest['stations'][0]['t2m_max'] = 22.4;
    files['latest.json'] = jsonEncode(customLatest);

    await pumpApp(tester, files: files, tileProvider: BlankTileProvider());
    await tester.tap(find.text(en.stationsViewMap));
    await tester.pumpAndSettle();

    // Both toggle buttons exist
    expect(find.byKey(const ValueKey('map_satellite_toggle')), findsOneWidget);
    expect(find.byKey(const ValueKey('map_temp_toggle')), findsOneWidget);

    // Initial state: OSM TileLayer and OSM attribution
    final initialAttribution =
        tester.widget<RichAttributionWidget>(find.byType(RichAttributionWidget));
    expect(
      initialAttribution.attributions
          .whereType<TextSourceAttribution>()
          .map((a) => a.text),
      contains(kPrismaTileAttribution),
    );
    expect(
      initialAttribution.attributions
          .whereType<TextSourceAttribution>()
          .map((a) => a.text),
      isNot(contains(kPrismaGibsAttribution)),
    );

    final initialTileLayer = tester.widget<TileLayer>(find.byType(TileLayer));
    expect(initialTileLayer.urlTemplate, contains('tile.openstreetmap.org'));

    // Tap SAT toggle button to activate NASA GIBS satellite
    await tester.tap(find.byKey(const ValueKey('map_satellite_toggle')));
    await tester.pumpAndSettle();

    // Switched to NASA GIBS TileLayer and attribution
    final gibsAttribution =
        tester.widget<RichAttributionWidget>(find.byType(RichAttributionWidget));
    expect(
      gibsAttribution.attributions
          .whereType<TextSourceAttribution>()
          .map((a) => a.text),
      contains(kPrismaGibsAttribution),
    );
    expect(
      gibsAttribution.attributions
          .whereType<TextSourceAttribution>()
          .map((a) => a.text),
      isNot(contains(kPrismaTileAttribution)),
    );

    final gibsTileLayer = tester.widget<TileLayer>(find.byType(TileLayer));
    expect(gibsTileLayer.urlTemplate, contains('gibs.earthdata.nasa.gov'));
    expect(
      gibsTileLayer.urlTemplate,
      contains('VIIRS_SNPP_CorrectedReflectance_TrueColor'),
    );
    expect(gibsTileLayer.maxNativeZoom, 9);
    expect(gibsTileLayer.maxZoom, 10.0);

    // Tap SAT toggle button again to return to OSM
    await tester.tap(find.byKey(const ValueKey('map_satellite_toggle')));
    await tester.pumpAndSettle();

    final revertedAttribution =
        tester.widget<RichAttributionWidget>(find.byType(RichAttributionWidget));
    expect(
      revertedAttribution.attributions
          .whereType<TextSourceAttribution>()
          .map((a) => a.text),
      contains(kPrismaTileAttribution),
    );
    expect(
      revertedAttribution.attributions
          .whereType<TextSourceAttribution>()
          .map((a) => a.text),
      isNot(contains(kPrismaGibsAttribution)),
    );
    final revertedTileLayer = tester.widget<TileLayer>(find.byType(TileLayer));
    expect(revertedTileLayer.urlTemplate, contains('tile.openstreetmap.org'));
  });

  testWidgets('the map shows the user position and its link line',
      (tester) async {
    final provider = FakeLocationProvider(
      () async => const GeoPoint(lat: -34.6, lon: -58.4),
    );
    await pumpApp(
      tester,
      locationProvider: provider,
      tileProvider: BlankTileProvider(),
    );
    await tester.tap(find.text(en.useMyLocation));
    await tester.pumpAndSettle();
    await dismissNearestCard(tester);

    await tester.tap(find.text(en.stationsViewMap));
    await tester.pumpAndSettle();

    expect(find.byTooltip(en.yourLocation), findsOneWidget);
    expect(find.byType(PolylineLayer), findsOneWidget);
  });

  testWidgets('a failed place load is reported and retried on the next query',
      (tester) async {
    final files = defaultFiles();
    var placesFail = true;
    final client = MockClient((request) async {
      final path = request.url.path.replaceFirst('/data/', '');
      if (placesFail && path.startsWith('places/')) {
        return http.Response('boom', 500);
      }
      final body = files[path];
      if (body == null) {
        return http.Response('not found', 404);
      }
      return ok(body);
    });
    await pumpApp(tester, client: client);

    await tester.enterText(find.byType(TextField), 'cordoba');
    await tester.pumpAndSettle();
    expect(find.text(en.placesUnavailable), findsOneWidget);

    placesFail = false;
    await tester.enterText(find.byType(TextField), 'cordob');
    await tester.pumpAndSettle();
    expect(find.text(en.placesUnavailable), findsNothing);
    expect(find.text(en.searchPlacesGroup), findsOneWidget);
  });

  testWidgets('Use my location shows the nearest station to the user', (tester) async {
    final provider = FakeLocationProvider(
      () async => const GeoPoint(lat: -34.6, lon: -58.4),
    );
    await pumpApp(tester, locationProvider: provider);
    await tester.tap(find.text(en.useMyLocation));
    await tester.pumpAndSettle();

    expect(find.textContaining('Nearest station: Buenos Aires Observatorio'),
        findsOneWidget);
    expect(find.textContaining('Distance:'), findsOneWidget);
    expect(find.text(en.nearestStationWarning), findsNothing);
  });

  for (final entry in {
    LocationErrorKind.denied: en.locationDenied,
    LocationErrorKind.unavailable: en.locationUnavailable,
    LocationErrorKind.timeout: en.locationTimeout,
  }.entries) {
    testWidgets('Use my location reports ${entry.key.name}', (tester) async {
      final provider = FakeLocationProvider(
        () async => throw LocationException(entry.key),
      );
      await pumpApp(tester, locationProvider: provider);
      await tester.tap(find.text(en.useMyLocation));
      await tester.pumpAndSettle();

      expect(find.text(entry.value), findsOneWidget);
      expect(find.text(en.useMyLocation), findsOneWidget);
    });
  }

  testWidgets('selecting a station opens the forecast with local issue time', (tester) async {
    await pumpApp(tester, size: const Size(1200, 3000));
    await tester.tap(find.text('La Quiaca Observatorio'));
    await tester.pumpAndSettle();
    expect(find.text(en.variableT2mMax), findsOneWidget);
    expect(find.text(en.variableT2mMin), findsOneWidget);
    expect(find.textContaining('13/11/2026 21:16'), findsOneWidget);
    expect(find.textContaining('UTC−3'), findsOneWidget);
    expect(find.textContaining(en.rawBanner), findsOneWidget);
  });

  testWidgets('forecast shows a missing_members case as no data, never interpolated',
      (tester) async {
    await pumpApp(tester, size: const Size(1200, 3000));
    await openForecast(tester);
    expect(find.textContaining('0/51 members'), findsWidgets);
    expect(find.text(en.missingMembersTitle), findsWidgets);
    expect(find.textContaining(en.legendModelsNeverPooled), findsWidgets);
  });

  testWidgets('forecast shows precip fractions and the observed series', (tester) async {
    await pumpApp(tester, size: const Size(1200, 3000));
    await openForecast(tester);
    expect(find.text(en.precipTitle), findsOneWidget);
    expect(find.text('71 %'), findsWidgets);
    await tester.scrollUntilVisible(
      find.text(en.observedTitle),
      400,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text(en.observedTitle), findsOneWidget);
    expect(find.text('14/10/2026'), findsWidgets);
    expect(find.text('21.8 °C'), findsWidgets);
  });

  testWidgets('forecast source comparison keeps models side by side, never pooled',
      (tester) async {
    await pumpApp(tester, size: const Size(1200, 3000));
    await openForecast(tester);
    expect(find.text(en.comparatorTitle), findsOneWidget);
    expect(find.textContaining(en.comparatorNote), findsOneWidget);
    expect(find.textContaining('GFS'), findsWidgets);
    expect(find.textContaining('ECMWF'), findsWidgets);
    expect(find.textContaining(en.legendModelsNeverPooled), findsWidgets);
  });

  testWidgets('Skill shows hindcast mean CRPSS and the closed operational gate',
      (tester) async {
    await pumpApp(tester, size: const Size(1200, 1400));
    await tester.tap(find.text(en.tabSkill));
    await tester.pumpAndSettle();
    expect(find.text(en.skillTitle), findsOneWidget);
    expect(find.textContaining(en.skillHindcastBanner), findsOneWidget);
    expect(find.text(en.skillMeanEmos), findsOneWidget);
    expect(find.text('-0.0774'), findsOneWidget);
    expect(find.text(en.skillMeanQm), findsOneWidget);
    expect(find.text('0.0002'), findsOneWidget);
    expect(find.textContaining(en.skillCellsCount(19, 19)), findsOneWidget);
    expect(find.textContaining(en.skillDidNotBeat), findsOneWidget);
    expect(find.text(en.skillGateClosed), findsOneWidget);
    expect(find.text(en.skillGateArchived(3, 15)), findsOneWidget);
    expect(find.textContaining('operational leaderboard'), findsWidgets);
  });

  testWidgets('Skill renders operational leaderboard with locked progress indicator',
      (tester) async {
    await pumpApp(tester, size: const Size(1200, 1400));
    await tester.tap(find.text(en.tabSkill));
    await tester.pumpAndSettle();
    expect(find.text('Operational verification leaderboard'), findsWidgets);
    expect(find.textContaining('13 of 15 (2 remaining)'), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
  });

  testWidgets('Skill renders operational leaderboard table when gate is unlocked',
      (tester) async {
    final unlockedFiles = {
      ...defaultFiles(),
      'leaderboard.json': fixture('leaderboard_unlocked.json'),
    };
    await pumpApp(tester, files: unlockedFiles, size: const Size(1200, 1400));
    await tester.tap(find.text(en.tabSkill));
    await tester.pumpAndSettle();

    expect(find.text('Operational verification leaderboard'), findsWidgets);
    // When unlocked, no LinearProgressIndicator is rendered
    expect(find.byType(LinearProgressIndicator), findsNothing);
    // Table renders the station and model labels
    expect(find.text('Alfa'), findsWidgets);
    expect(find.text('GFS'), findsWidgets);
    expect(find.text('ECMWF'), findsWidgets);
    // Valid numbers for sufficient cell and summary chips
    expect(find.text('0.5000'), findsNWidgets(2));
    expect(find.text('0.7500'), findsNWidgets(2));
    // Insufficient dashes
    expect(find.text('—'), findsWidgets);
  });

  testWidgets('About / Status shows the app status texts and the attribution links',
      (tester) async {
    await pumpApp(tester, size: const Size(1200, 1400));
    await tester.tap(find.text(en.tabAbout));
    await tester.pumpAndSettle();
    expect(find.textContaining(en.statusForecasts), findsOneWidget);
    expect(find.textContaining('15-issue-date gate'), findsWidgets);
    await tester.scrollUntilVisible(
      find.text('Weather data by Open-Meteo.com'),
      400,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Weather data by Open-Meteo.com'), findsOneWidget);
    expect(find.text('CC BY 2.5 AR'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text(en.aboutMachineTranslations),
      400,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.textContaining(en.aboutMachineTranslations), findsOneWidget);
  });

  testWidgets('a network failure is shown with a retry action', (tester) async {
    final client = MockClient((request) async => http.Response('boom', 500));
    await pumpApp(tester, client: client);
    expect(find.textContaining('Could not read'), findsOneWidget);
    expect(find.textContaining('HTTP 500'), findsOneWidget);
    expect(find.text(en.retry), findsOneWidget);
    expect(find.text(en.tabStations), findsNothing);
  });

  testWidgets('an unsupported schema version is rejected with a clear message',
      (tester) async {
    final files = defaultFiles();
    files['latest.json'] = files['latest.json']!.replaceFirst('"1.0"', '"2.0"');
    await pumpApp(tester, files: files);
    expect(find.textContaining('is not supported'), findsOneWidget);
    expect(find.textContaining('"2.0"'), findsOneWidget);
  });

  testWidgets('a corrupted latest.json shows the English error and a working Retry',
      (tester) async {
    final files = defaultFiles();
    files['latest.json'] = '{not json';
    await pumpApp(tester, files: files);
    expect(find.textContaining('Invalid JSON in latest.json'), findsOneWidget);
    expect(find.textContaining('inválido'), findsNothing);
    expect(find.text(en.retry), findsOneWidget);

    files['latest.json'] = fixture('latest.json');
    await tester.tap(find.text(en.retry));
    await tester.pumpAndSettle();
    expect(find.text('2 stations'), findsOneWidget);
    expect(find.text(en.tabStations), findsOneWidget);
  });

  testWidgets('phone width stays usable and keeps the four screens', (tester) async {
    await pumpApp(tester, size: const Size(360, 780));
    expect(tester.takeException(), isNull);
    expect(find.text(en.tabStations), findsOneWidget);
    expect(find.text(en.tabForecast), findsOneWidget);
    expect(find.text(en.tabSkill), findsOneWidget);
    expect(find.text(en.tabAbout), findsOneWidget);

    await tester.tap(find.text(en.tabForecast));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text(en.variableT2mMax), findsOneWidget);
  });

  testWidgets('forecast chart displays climatological normal legend and renders band',
      (tester) async {
    await pumpApp(tester, size: const Size(1200, 3000));
    await openForecast(tester);
    expect(find.textContaining(en.legendClimatology), findsWidgets);
    expect(find.byType(ForecastBandChart), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('ForecastBandChart paints with climatology range without exceptions in dark and light mode',
      (tester) async {
    final chart = ForecastBandChart(
      leads: const [0, 1, 2, 3],
      series: const [],
      noDataLabel: 'no data',
      climatology: const ClimatologyRange(low: 12.0, high: 26.0, median: 19.0),
      climatologyLabel: 'Normal range',
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData.light(),
        darkTheme: ThemeData.dark(),
        themeMode: ThemeMode.light,
        home: Scaffold(body: SizedBox(width: 400, height: 300, child: chart)),
      ),
    );
    expect(tester.takeException(), isNull);

    // Switch to dark theme
    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData.light(),
        darkTheme: ThemeData.dark(),
        themeMode: ThemeMode.dark,
        home: Scaffold(body: SizedBox(width: 400, height: 300, child: chart)),
      ),
    );
    expect(tester.takeException(), isNull);
  });
}
