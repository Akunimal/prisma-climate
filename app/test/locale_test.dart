import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:material_ui/material_ui.dart';
import 'package:prisma_app/l10n/generated/app_localizations_en.dart';
import 'package:prisma_app/src/app.dart';
import 'package:prisma_app/src/data/repository.dart';
import 'package:prisma_app/src/l10n.dart';
import 'package:shared_preferences/shared_preferences.dart';

String fixture(String name) => File('test/fixtures/$name').readAsStringSync();

final AppLocalizationsEn en = AppLocalizationsEn();

Map<String, String> defaultFiles() => {
      'latest.json': fixture('latest.json'),
      'about.json': fixture('about.json'),
      'skill.json': fixture('skill.json'),
      'stations/la_quiaca.json': fixture('stations/la_quiaca.json'),
      'stations/buenos_aires.json': fixture('stations/buenos_aires.json'),
    };

http.Response ok(String body) => http.Response.bytes(
      utf8.encode(body),
      200,
      headers: const {'content-type': 'application/json; charset=utf-8'},
    );

/// Mock client that records every path it served, so a locale switch can be
/// shown not to re-fetch anything.
http.Client recordingClient(Map<String, String> files, List<String> log) {
  return MockClient((request) async {
    final path = request.url.path.replaceFirst('/data/', '');
    log.add(path);
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
    client: client ?? recordingClient(files ?? defaultFiles(), <String>[]),
    baseUrl: 'https://example.test/data/',
  );
  await tester.pumpWidget(PrismaApp(repository: repository));
  await tester.pumpAndSettle();
}

Future<void> pickLanguage(WidgetTester tester, String endonym) async {
  await tester.tap(find.byIcon(Icons.language));
  await tester.pumpAndSettle();
  await tester.tap(find.text(endonym));
  await tester.pumpAndSettle();
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets('picking a language rewrites all three screens without re-fetching',
      (tester) async {
    final log = <String>[];
    await pumpApp(
      tester,
      client: recordingClient(defaultFiles(), log),
      size: const Size(1200, 3000),
    );

    expect(find.text('Stations'), findsOneWidget);
    await tester.tap(find.text('La Quiaca Observatorio'));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.textContaining('21.8 °C'),
      400,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.textContaining('21.8 °C'), findsWidgets);
    final requestsAfterLoad = log.length;

    await pickLanguage(tester, kLocaleEndonyms['es']!);
    expect(log.length, requestsAfterLoad, reason: 'locale switch re-fetched');

    // The forecast list was scrolled down to the observed value; bring the
    // variable title back into view before asserting its Spanish text.
    await tester.scrollUntilVisible(
      find.text('Máxima diaria (t2m_max)'),
      -400,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.textContaining('21,8 °C'), findsWidgets);
    expect(find.text(en.variableT2mMax), findsNothing);
    expect(find.text('Máxima diaria (t2m_max)'), findsOneWidget);

    await tester.tap(find.text('Estaciones'));
    await tester.pumpAndSettle();
    expect(find.text('2 estaciones'), findsOneWidget);

    await tester.tap(find.text('Acerca de / Estado'));
    await tester.pumpAndSettle();
    expect(find.textContaining('sin corrección de sesgo'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'first visit with no saved choice stays English on a German platform locale',
      (tester) async {
    tester.binding.platformDispatcher.localeTestValue =
        const Locale('de', 'DE');
    tester.binding.platformDispatcher.localesTestValue = const <Locale>[
      Locale('de', 'DE'),
    ];
    addTearDown(tester.binding.platformDispatcher.clearLocaleTestValue);
    addTearDown(tester.binding.platformDispatcher.clearLocalesTestValue);
    await pumpApp(tester);

    final resolved =
        Localizations.localeOf(tester.element(find.byType(AppBar)));
    expect(resolved.languageCode, 'en',
        reason: 'platform locale leaked into the app locale: $resolved');
    expect(find.text('Stations'), findsOneWidget);
    expect(find.text('Stationen'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('the persisted locale is restored and updated on every pick',
      (tester) async {
    SharedPreferences.setMockInitialValues({
      'prisma_ui_locale': 'de',
    });
    await pumpApp(tester);

    expect(find.text('Stationen'), findsOneWidget);
    expect(find.text('2 Stationen'), findsOneWidget);

    await pickLanguage(tester, kLocaleEndonyms['it']!);
    expect(find.text('Stazioni'), findsOneWidget);
    expect(find.text('2 stazioni'), findsOneWidget);

    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('prisma_ui_locale'), 'it');
  });

  testWidgets('the error state renders fully in Spanish', (tester) async {
    SharedPreferences.setMockInitialValues({
      'prisma_ui_locale': 'es',
    });
    final client = MockClient((request) async => http.Response('boom', 500));
    await pumpApp(tester, client: client);

    expect(find.textContaining('No se pudo leer'), findsOneWidget);
    expect(find.textContaining('HTTP 500'), findsOneWidget);
    expect(find.text('Reintentar'), findsOneWidget);
    expect(find.textContaining('Could not read'), findsNothing);
    expect(find.text('Retry'), findsNothing);
  });

  testWidgets('the no-data forecast state renders fully in Spanish',
      (tester) async {
    SharedPreferences.setMockInitialValues({
      'prisma_ui_locale': 'es',
    });
    await pumpApp(tester, size: const Size(1200, 3000));

    await tester.tap(find.text('Pronóstico'));
    await tester.pumpAndSettle();
    expect(find.textContaining('sin datos (0/51 miembros)'), findsWidgets);
    expect(find.text('Sin datos'), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Cyrillic, CJK and Devanagari locales render without exceptions',
      (tester) async {
    await pumpApp(tester);

    await pickLanguage(tester, kLocaleEndonyms['ru']!);
    expect(find.text('Станции'), findsOneWidget);
    expect(find.text('2 станции'), findsOneWidget);
    expect(tester.takeException(), isNull);

    await pickLanguage(tester, kLocaleEndonyms['zh']!);
    expect(find.text('观测站'), findsOneWidget);
    expect(tester.takeException(), isNull);

    await pickLanguage(tester, kLocaleEndonyms['ja']!);
    expect(find.text('観測所'), findsOneWidget);
    expect(tester.takeException(), isNull);

    await pickLanguage(tester, kLocaleEndonyms['hi']!);
    expect(find.text('स्टेशन'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
