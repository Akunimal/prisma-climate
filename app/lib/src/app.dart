import 'package:material_ui/material_ui.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'data/models.dart';
import 'data/repository.dart';
import 'l10n.dart';
import 'screens/about_screen.dart';
import 'screens/forecast_screen.dart';
import 'screens/stations_screen.dart';
import 'widgets/common.dart';
import 'widgets/language_menu.dart';

class PrismaApp extends StatefulWidget {
  const PrismaApp({super.key, required this.repository});

  final PrismaRepository repository;

  @override
  State<PrismaApp> createState() => _PrismaAppState();
}

class _PrismaAppState extends State<PrismaApp> {
  static const String _prefsKey = 'prisma_ui_locale';

  /// `null` = follow the browser language (auto-detection).
  Locale? _locale;

  @override
  void initState() {
    super.initState();
    _restoreLocale();
  }

  Future<void> _restoreLocale() async {
    final prefs = await SharedPreferences.getInstance();
    final code = prefs.getString(_prefsKey);
    if (!mounted || code == null) {
      return;
    }
    setState(() => _locale = Locale(code));
  }

  Future<void> _pickLocale(Locale locale) async {
    setState(() => _locale = locale);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefsKey, locale.languageCode);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      locale: _locale,
      supportedLocales: kSupportedLocales,
      localizationsDelegates: kLocalizationsDelegates,
      debugShowCheckedModeBanner: false,
      onGenerateTitle: (context) => context.l10n.appTitle,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0B6B45)),
      ),
      home: HomeShell(
        repository: widget.repository,
        onLocalePicked: _pickLocale,
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
  });

  final PrismaRepository repository;
  final ValueChanged<Locale> onLocalePicked;

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

  List<Widget> _appBarActions(BuildContext context) => [
        LanguageMenu(onSelected: widget.onLocalePicked),
      ];

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
        ),
      1 => ForecastScreen(
          repository: widget.repository,
          latest: bootstrap.latest,
          about: bootstrap.about,
          stationId: stationId,
          onStationChanged: (id) => setState(() => _stationId = id),
        ),
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
