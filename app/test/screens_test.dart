import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:material_ui/material_ui.dart';
import 'package:prisma_app/l10n/generated/app_localizations_en.dart';
import 'package:prisma_app/src/app.dart';
import 'package:prisma_app/src/data/repository.dart';
import 'package:shared_preferences/shared_preferences.dart';

String fixture(String name) => File('test/fixtures/$name').readAsStringSync();

/// English strings as the running app renders them under the default locale.
final AppLocalizationsEn en = AppLocalizationsEn();

Map<String, String> defaultFiles() => {
      'latest.json': fixture('latest.json'),
      'about.json': fixture('about.json'),
      'stations/la_quiaca.json': fixture('stations/la_quiaca.json'),
      'stations/buenos_aires.json': fixture('stations/buenos_aires.json'),
    };

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
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final repository = PrismaRepository(
    client: client ?? mockClient(files ?? defaultFiles()),
    baseUrl: 'https://example.test/data/',
  );
  await tester.pumpWidget(PrismaApp(repository: repository));
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
    expect(find.text(en.observedTitle), findsOneWidget);
    expect(find.text('14/10/2026'), findsWidgets);
    expect(find.text('21.8 °C'), findsWidgets);
  });

  testWidgets('About / Status shows the app status texts and the attribution links',
      (tester) async {
    await pumpApp(tester);
    await tester.tap(find.text(en.tabAbout));
    await tester.pumpAndSettle();
    expect(find.textContaining(en.statusForecasts), findsOneWidget);
    expect(find.textContaining('15-issue-date gate'), findsWidgets);
    await tester.scrollUntilVisible(
      find.text(en.aboutMachineTranslations),
      500,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.textContaining(en.aboutMachineTranslations), findsOneWidget);
    expect(find.text('Weather data by Open-Meteo.com'), findsOneWidget);
    expect(find.text('CC BY 2.5 AR'), findsOneWidget);
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

  testWidgets('phone width stays usable and keeps the three screens', (tester) async {
    await pumpApp(tester, size: const Size(360, 780));
    expect(tester.takeException(), isNull);
    expect(find.text(en.tabStations), findsOneWidget);
    expect(find.text(en.tabForecast), findsOneWidget);
    expect(find.text(en.tabAbout), findsOneWidget);

    await tester.tap(find.text(en.tabForecast));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text(en.variableT2mMax), findsOneWidget);
  });
}
