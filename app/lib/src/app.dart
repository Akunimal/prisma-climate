import 'package:flutter_map/flutter_map.dart';
import 'package:material_ui/material_ui.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'data/models.dart';
import 'data/repository.dart';
import 'l10n.dart';
import 'location_provider.dart';
import 'screens/about_screen.dart';
import 'screens/forecast_screen.dart';
import 'screens/skill_screen.dart';
import 'screens/stations_screen.dart';
import 'widgets/common.dart';
import 'widgets/language_menu.dart';

class PrismaApp extends StatefulWidget {
  const PrismaApp({
    super.key,
    required this.repository,
    this.locationProvider,
    this.tileProvider,
  });

  final PrismaRepository repository;
  final LocationProvider? locationProvider;
  final TileProvider? tileProvider;

  @override
  State<PrismaApp> createState() => _PrismaAppState();
}

class _PrismaAppState extends State<PrismaApp> {
  static const String _prefsKey = 'prisma_ui_locale';
  static const String _themePrefsKey = 'prisma_theme_mode';

  /// Always set: the app starts in English on a first visit and never resolves
  /// from the browser/system locale. Only a saved `prisma_ui_locale` moves it.
  Locale _locale = const Locale('en');
  ThemeMode _themeMode = ThemeMode.system;

  @override
  void initState() {
    super.initState();
    _restoreLocale();
    _restoreThemeMode();
  }

  Future<void> _restoreLocale() async {
    final prefs = await SharedPreferences.getInstance();
    final code = prefs.getString(_prefsKey);
    if (!mounted || code == null) {
      return;
    }
    setState(() => _locale = Locale(code));
  }

  Future<void> _restoreThemeMode() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_themePrefsKey);
    final restored = switch (raw) {
      'light' => ThemeMode.light,
      'dark' => ThemeMode.dark,
      _ => ThemeMode.system,
    };
    if (!mounted) return;
    setState(() {
      _themeMode = restored;
    });
  }

  Future<void> _pickLocale(Locale locale) async {
    setState(() => _locale = locale);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefsKey, locale.languageCode);
  }

  Future<void> _pickThemeMode(ThemeMode mode) async {
    setState(() {
      _themeMode = mode;
    });
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_themePrefsKey, mode.name);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      locale: _locale,
      supportedLocales: kSupportedLocales,
      localizationsDelegates: kLocalizationsDelegates,
      debugShowCheckedModeBanner: false,
      onGenerateTitle: (context) => context.l10n.appTitle,
      themeMode: _themeMode,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.light,
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0B6B45)),
      ),
      darkTheme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF0B6B45),
          brightness: Brightness.dark,
        ),
      ),
      home: HomeShell(
        repository: widget.repository,
        locationProvider: widget.locationProvider,
        tileProvider: widget.tileProvider,
        onLocalePicked: _pickLocale,
        currentThemeMode: _themeMode,
        onThemeModePicked: _pickThemeMode,
      ),
    );
  }
}

class _Bootstrap {
  const _Bootstrap(this.latest, this.about);

  final LatestDocument latest;
  final AboutDocument about;
}

class HomeShell extends StatefulWidget {
  const HomeShell({
    super.key,
    required this.repository,
    required this.onLocalePicked,
    this.locationProvider,
    this.tileProvider,
    this.currentThemeMode = ThemeMode.system,
    this.onThemeModePicked,
  });

  final PrismaRepository repository;
  final ValueChanged<Locale> onLocalePicked;
  final LocationProvider? locationProvider;
  final TileProvider? tileProvider;
  final ThemeMode currentThemeMode;
  final ValueChanged<ThemeMode>? onThemeModePicked;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  late Future<_Bootstrap> _bootstrap;
  int _tab = 0;
  String? _stationId;

  @override
  void initState() {
    super.initState();
    _bootstrap = _load();
  }

  Future<_Bootstrap> _load() async {
    final results = await Future.wait<Object>([
      widget.repository.loadLatest(),
      widget.repository.loadAbout(),
    ]);
    return _Bootstrap(
      results[0] as LatestDocument,
      results[1] as AboutDocument,
    );
  }

  void _retry() {
    final future = _load();
    setState(() {
      _bootstrap = future;
    });
  }

  void _selectStation(String id) {
    setState(() {
      _stationId = id;
      _tab = 1;
    });
  }

  List<Widget> _appBarActions(BuildContext context) {
    final isDark = widget.currentThemeMode == ThemeMode.dark ||
        (widget.currentThemeMode == ThemeMode.system &&
            Theme.of(context).colorScheme.brightness == Brightness.dark);
    return [
      IconButton(
        key: const ValueKey('theme_toggle_button'),
        icon: Icon(isDark ? Icons.light_mode : Icons.dark_mode),
        tooltip: 'Toggle dark theme',
        onPressed: () {
          widget.onThemeModePicked
              ?.call(isDark ? ThemeMode.light : ThemeMode.dark);
        },
      ),
      LanguageMenu(onSelected: widget.onLocalePicked),
    ];
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return FutureBuilder<_Bootstrap>(
      future: _bootstrap,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return Scaffold(
            appBar: AppBar(
              title: Text(l10n.appTitle),
              actions: _appBarActions(context),
            ),
            body: const SafeArea(child: LoadingView()),
          );
        }
        if (snapshot.hasError) {
          return Scaffold(
            appBar: AppBar(
              title: Text(l10n.appTitle),
              actions: _appBarActions(context),
            ),
            body: SafeArea(
              child: ErrorView(
                title: l10n.errorTitle('latest.json / about.json'),
                message: describeError(context, snapshot.error!),
                onRetry: _retry,
              ),
            ),
          );
        }
        final bootstrap = snapshot.data!;
        if (bootstrap.latest.stations.isEmpty) {
          return Scaffold(
            appBar: AppBar(
              title: Text(l10n.appTitle),
              actions: _appBarActions(context),
            ),
            body: Center(child: Text(l10n.noData)),
          );
        }
        return _buildShell(context, bootstrap);
      },
    );
  }

  Widget _buildShell(BuildContext context, _Bootstrap bootstrap) {
    final l10n = context.l10n;
    final stationId = _stationId ?? bootstrap.latest.stations.first.id;
    final body = switch (_tab) {
      0 => StationsScreen(
          latest: bootstrap.latest,
          selectedId: stationId,
          onSelect: _selectStation,
          repository: widget.repository,
          regionId: bootstrap.about.region.id,
          locationProvider: widget.locationProvider,
          tileProvider: widget.tileProvider,
        ),
      1 => ForecastScreen(
          repository: widget.repository,
          latest: bootstrap.latest,
          about: bootstrap.about,
          stationId: stationId,
          onStationChanged: (id) => setState(() => _stationId = id),
        ),
      2 => SkillScreen(repository: widget.repository),
      _ => AboutScreen(about: bootstrap.about, latest: bootstrap.latest),
    };

    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 840;
        final destinations = [
          NavigationDestination(
            icon: const Icon(Icons.list_alt),
            label: l10n.tabStations,
          ),
          NavigationDestination(
            icon: const Icon(Icons.show_chart),
            label: l10n.tabForecast,
          ),
          NavigationDestination(
            icon: const Icon(Icons.speed),
            label: l10n.tabSkill,
          ),
          NavigationDestination(
            icon: const Icon(Icons.info_outline),
            label: l10n.tabAbout,
          ),
        ];

        if (!wide) {
          return Scaffold(
            appBar: AppBar(
              title: Text(
                l10n.appTitle,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              actions: _appBarActions(context),
            ),
            body: SafeArea(child: body),
            bottomNavigationBar: NavigationBar(
              selectedIndex: _tab,
              onDestinationSelected: (index) => setState(() => _tab = index),
              destinations: destinations,
            ),
          );
        }

        return Scaffold(
          appBar: AppBar(
            title: Text(l10n.appTitle),
            actions: _appBarActions(context),
          ),
          body: Row(
            children: [
              NavigationRail(
                selectedIndex: _tab,
                onDestinationSelected: (index) => setState(() => _tab = index),
                labelType: NavigationRailLabelType.all,
                destinations: [
                  for (final destination in destinations)
                    NavigationRailDestination(
                      icon: destination.icon,
                      label: Text(destination.label),
                    ),
                ],
              ),
              const VerticalDivider(width: 1),
              Expanded(
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 980),
                    child: body,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
