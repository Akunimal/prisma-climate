import 'package:material_ui/material_ui.dart';

import 'data/models.dart';
import 'data/repository.dart';
import 'screens/about_screen.dart';
import 'screens/forecast_screen.dart';
import 'screens/stations_screen.dart';
import 'strings.dart';
import 'widgets/common.dart';

class PrismaApp extends StatelessWidget {
  const PrismaApp({super.key, required this.repository});

  final PrismaRepository repository;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: S.appTitle,
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0B6B45)),
      ),
      home: HomeShell(repository: repository),
    );
  }
}

class _Bootstrap {
  const _Bootstrap(this.latest, this.about);

  final LatestDocument latest;
  final AboutDocument about;
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key, required this.repository});

  final PrismaRepository repository;

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
    setState(() => _bootstrap = _load());
  }

  void _selectStation(String id) {
    setState(() {
      _stationId = id;
      _tab = 1;
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_Bootstrap>(
      future: _bootstrap,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Scaffold(
            body: SafeArea(child: LoadingView()),
          );
        }
        if (snapshot.hasError) {
          return Scaffold(
            body: SafeArea(
              child: ErrorView(
                title: S.errorTitle('latest.json / about.json'),
                message: describeError(snapshot.error!),
                onRetry: _retry,
              ),
            ),
          );
        }
        final bootstrap = snapshot.data!;
        if (bootstrap.latest.stations.isEmpty) {
          return Scaffold(
            appBar: AppBar(title: const Text(S.appTitle)),
            body: const Center(child: Text(S.noData)),
          );
        }
        return _buildShell(bootstrap);
      },
    );
  }

  Widget _buildShell(_Bootstrap bootstrap) {
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
          const NavigationDestination(
            icon: Icon(Icons.list_alt),
            label: S.tabStations,
          ),
          const NavigationDestination(
            icon: Icon(Icons.show_chart),
            label: S.tabForecast,
          ),
          const NavigationDestination(
            icon: Icon(Icons.info_outline),
            label: S.tabAbout,
          ),
        ];

        if (!wide) {
          return Scaffold(
            appBar: AppBar(
              title: const Text(
                S.appTitle,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
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
          appBar: AppBar(title: const Text(S.appTitle)),
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
