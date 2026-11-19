import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:material_ui/material_ui.dart';
import 'package:prisma_app/src/app.dart';
import 'package:prisma_app/src/data/repository.dart';
import 'package:prisma_app/src/widgets/common.dart';
import 'package:shared_preferences/shared_preferences.dart';

String fixture(String name) => File('test/fixtures/$name').readAsStringSync();

Map<String, String> defaultFiles() => {
      'latest.json': fixture('latest.json'),
      'about.json': fixture('about.json'),
      'skill.json': fixture('skill.json'),
      'stations/la_quiaca.json': fixture('stations/la_quiaca.json'),
      'stations/buenos_aires.json': fixture('stations/buenos_aires.json'),
      'places/index.json': fixture('places/index.json'),
      'places/ar.json': fixture('places/ar.json'),
    };

http.Client mockClient(Map<String, String> files) {
  return MockClient((request) async {
    final path = request.url.path.replaceFirst('/data/', '');
    final body = files[path];
    if (body == null) {
      return http.Response('not found', 404);
    }
    return http.Response.bytes(
      utf8.encode(body),
      200,
      headers: const {'content-type': 'application/json; charset=utf-8'},
    );
  });
}

Future<void> pumpPrismaApp(WidgetTester tester) async {
  tester.view.physicalSize = const Size(1200, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);

  final repository = PrismaRepository(
    client: mockClient(defaultFiles()),
    baseUrl: 'https://example.test/data/',
  );
  await tester.pumpWidget(PrismaApp(repository: repository));
  await tester.pumpAndSettle();
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets('initializes with ThemeMode.system and dual M3 themes',
      (tester) async {
    await pumpPrismaApp(tester);

    final app = tester.widget<MaterialApp>(find.byType(MaterialApp));
    expect(app.themeMode, ThemeMode.system);
    expect(app.theme?.useMaterial3, isTrue);
    expect(app.darkTheme?.useMaterial3, isTrue);
    expect(app.darkTheme?.brightness, Brightness.dark);
    expect(app.theme?.brightness, Brightness.light);
  });

  testWidgets('toggle button switches theme mode and persists in SharedPreferences',
      (tester) async {
    await pumpPrismaApp(tester);

    final toggleFinder = find.byKey(const ValueKey('theme_toggle_button'));
    expect(toggleFinder, findsOneWidget);

    // Initial state: ThemeMode.system -> toggle sets ThemeMode.dark (since default test brightness is light)
    await tester.tap(toggleFinder);
    await tester.pumpAndSettle();

    var app = tester.widget<MaterialApp>(find.byType(MaterialApp));
    expect(app.themeMode, ThemeMode.dark);

    var prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('prisma_theme_mode'), 'dark');

    // Tapping again switches back to ThemeMode.light
    await tester.tap(toggleFinder);
    await tester.pumpAndSettle();

    app = tester.widget<MaterialApp>(find.byType(MaterialApp));
    expect(app.themeMode, ThemeMode.light);

    prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('prisma_theme_mode'), 'light');
  });

  testWidgets('restores saved dark theme preference from SharedPreferences',
      (tester) async {
    SharedPreferences.setMockInitialValues({'prisma_theme_mode': 'dark'});
    await pumpPrismaApp(tester);

    final app = tester.widget<MaterialApp>(find.byType(MaterialApp));
    expect(app.themeMode, ThemeMode.dark);
  });

  testWidgets('modelColor provides dark-aware contrast for gfs_seamless',
      (tester) async {
    late BuildContext capturedLightContext;
    late BuildContext capturedDarkContext;

    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF0B6B45),
            brightness: Brightness.light,
          ),
        ),
        darkTheme: ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF0B6B45),
            brightness: Brightness.dark,
          ),
        ),
        themeMode: ThemeMode.light,
        home: Builder(
          builder: (context) {
            capturedLightContext = context;
            return const SizedBox();
          },
        ),
      ),
    );

    final lightColor = modelColor(capturedLightContext, 'gfs_seamless');
    expect(lightColor, const Color(0xFFB4531F));

    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData(
          useMaterial3: true,
          brightness: Brightness.light,
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF0B6B45),
            brightness: Brightness.light,
          ),
        ),
        darkTheme: ThemeData(
          useMaterial3: true,
          brightness: Brightness.dark,
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF0B6B45),
            brightness: Brightness.dark,
          ),
        ),
        themeMode: ThemeMode.dark,
        home: Builder(
          builder: (context) {
            capturedDarkContext = context;
            return const SizedBox();
          },
        ),
      ),
    );
    await tester.pumpAndSettle();

    final darkColor = modelColor(capturedDarkContext, 'gfs_seamless');
    expect(darkColor, const Color(0xFFFB923C));
  });
}
