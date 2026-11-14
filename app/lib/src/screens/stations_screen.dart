import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:material_ui/material_ui.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/models.dart';
import '../format.dart';
import '../l10n.dart';
import '../map_tiles.dart';
import '../station_bounds.dart';

String _normalize(String value) {
  const replacements = {
    'á': 'a',
    'à': 'a',
    'ä': 'a',
    'â': 'a',
    'ã': 'a',
    'é': 'e',
    'è': 'e',
    'ë': 'e',
    'ê': 'e',
    'í': 'i',
    'ì': 'i',
    'ï': 'i',
    'î': 'i',
    'ó': 'o',
    'ò': 'o',
    'ö': 'o',
    'ô': 'o',
    'õ': 'o',
    'ú': 'u',
    'ù': 'u',
    'ü': 'u',
    'û': 'u',
    'ñ': 'n',
  };
  var out = value.toLowerCase();
  replacements.forEach((key, plain) => out = out.replaceAll(key, plain));
  return out;
}

class StationsScreen extends StatefulWidget {
  const StationsScreen({
    super.key,
    required this.latest,
    required this.onSelect,
    this.selectedId,
    this.tileProvider,
  });

  final LatestDocument latest;
  final ValueChanged<String> onSelect;
  final String? selectedId;
  final TileProvider? tileProvider;

  @override
  State<StationsScreen> createState() => _StationsScreenState();
}

class _StationsScreenState extends State<StationsScreen> {
  final TextEditingController _controller = TextEditingController();
  String _query = '';
  bool _mapView = false;
  String? _selectedMarkerId;
  bool _tilesFailed = false;

  @override
  void initState() {
    super.initState();
    _loadView();
  }

  Future<void> _loadView() async {
    final prefs = await SharedPreferences.getInstance();
    final stored = prefs.getString('prisma_stations_view');
    if (!mounted) return;
    setState(() => _mapView = stored == 'map');
  }

  Future<void> _setView(bool map) async {
    setState(() => _mapView = map);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('prisma_stations_view', map ? 'map' : 'list');
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  List<StationSummary> get _filteredStations {
    final query = _normalize(_query.trim());
    return widget.latest.stations.where((station) {
      if (query.isEmpty) return true;
      return _normalize(station.name).contains(query) ||
          _normalize(station.climateZone).contains(query) ||
          _normalize(station.id).contains(query);
    }).toList();
  }

  Map<String, Color> _zoneColors() {
    final zones = widget.latest.stations.map((s) => s.climateZone).toSet().toList()..sort();
    const palette = <Color>[
      Color(0xFF1B9E77),
      Color(0xFFD95F02),
      Color(0xFF7570B3),
      Color(0xFFE7298A),
      Color(0xFF66A61E),
      Color(0xFFE6AB02),
      Color(0xFFA6761D),
      Color(0xFF666666),
    ];
    final out = <String, Color>{};
    for (var i = 0; i < zones.length; i++) {
      out[zones[i]] = palette[i % palette.length];
    }
    return out;
  }

  Future<void> _openCard(StationSummary station) async {
    setState(() => _selectedMarkerId = station.id);
    final width = MediaQuery.of(context).size.width;
    final l10n = context.l10n;
    final zoneColors = _zoneColors();
    final card = Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(station.name, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 4),
          Row(
            children: [
              Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(
                  color: zoneColors[station.climateZone],
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 6),
              Text('${l10n.labelClimateZone}: ${station.climateZone}'),
            ],
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: () {
              Navigator.of(context).pop();
              widget.onSelect(station.id);
            },
            child: Text(l10n.stationsViewForecast),
          ),
        ],
      ),
    );
    if (width < 600) {
      await showModalBottomSheet<void>(
        context: context,
        builder: (_) => card,
      );
    } else {
      await showDialog<void>(
        context: context,
        builder: (_) => AlertDialog(
          content: card,
        ),
      );
    }
    if (mounted) setState(() => _selectedMarkerId = null);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = context.l10n;
    final filtered = _filteredStations;
    final zoneColors = _zoneColors();
    final zones = widget.latest.stations.map((s) => s.climateZone).toSet().toList()..sort();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  l10n.stationCount(widget.latest.stations.length),
                  style: theme.textTheme.titleSmall,
                ),
              ),
              Text(
                widget.latest.issueDate,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 6),
          child: TextField(
            controller: _controller,
            onChanged: (value) => setState(() => _query = value),
            decoration: InputDecoration(
              hintText: l10n.searchHint,
              prefixIcon: const Icon(Icons.search),
              isDense: true,
              border: const OutlineInputBorder(),
              suffixIcon: _query.isEmpty
                  ? null
                  : IconButton(
                      tooltip: l10n.clearSearch,
                      icon: const Icon(Icons.clear),
                      onPressed: () {
                        _controller.clear();
                        setState(() => _query = '');
                      },
                    ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 2, 16, 4),
          child: Text(
            l10n.stationsIntro,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 4),
          child: SegmentedButton<bool>(
            segments: [
              ButtonSegment<bool>(
                value: false,
                label: Text(l10n.stationsViewList),
                icon: const Icon(Icons.list),
              ),
              ButtonSegment<bool>(
                value: true,
                label: Text(l10n.stationsViewMap),
                icon: const Icon(Icons.map),
              ),
            ],
            selected: <bool>{_mapView},
            onSelectionChanged: (selection) => _setView(selection.first),
          ),
        ),
        Expanded(
          child: _mapView
              ? _buildMap(context, filtered, zones, zoneColors, l10n, theme)
              : (filtered.isEmpty
                  ? EmptyState(message: l10n.searchNoResults)
                  : ListView.separated(
                      padding: const EdgeInsets.fromLTRB(8, 4, 8, 16),
                      itemCount: filtered.length,
                      separatorBuilder: (_, _) => const Divider(height: 1),
                      itemBuilder: (context, index) {
                        final station = filtered[index];
                        final selected = station.id == widget.selectedId;
                        return ListTile(
                          selected: selected,
                          title: Text(station.name),
                          subtitle: Text(
                            '${station.climateZone} · ${coordinates(station.lat, station.lon, locale: context.localeTag)}',
                          ),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => widget.onSelect(station.id),
                        );
                      },
                    )),
        ),
      ],
    );
  }

  Widget _buildMap(
    BuildContext context,
    List<StationSummary> filtered,
    List<String> zones,
    Map<String, Color> zoneColors,
    dynamic l10n,
    ThemeData theme,
  ) {
    final allBounds = computeStationBounds(widget.latest.stations);
    final cameraFit = allBounds != null
        ? CameraFit.bounds(bounds: allBounds, padding: const EdgeInsets.all(48))
        : null;

    return Stack(
      children: [
        FlutterMap(
          options: MapOptions(
            initialCameraFit: cameraFit,
            interactionOptions: const InteractionOptions(
              flags: InteractiveFlag.all & ~InteractiveFlag.rotate,
            ),
            minZoom: 3,
            maxZoom: 10,
          ),
          children: [
            TileLayer(
              urlTemplate: kPrismaTileUrlTemplate,
              tileProvider: widget.tileProvider ?? NetworkTileProvider(),
              userAgentPackageName: kPrismaTileUserAgent,
              errorTileCallback: (tile, error, stackTrace) {
                if (!_tilesFailed && mounted) {
                  setState(() => _tilesFailed = true);
                }
              },
            ),
            MarkerLayer(
              markers: filtered.map((station) {
                final selected = station.id == _selectedMarkerId;
                return Marker(
                  point: LatLng(station.lat, station.lon),
                  width: 44,
                  height: 44,
                  child: Semantics(
                    label: station.name,
                    button: true,
                    child: GestureDetector(
                      onTap: () => _openCard(station),
                      child: Tooltip(
                        message: station.name,
                        child: Container(
                          decoration: BoxDecoration(
                            color: zoneColors[station.climateZone],
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: selected ? Colors.white : Colors.black54,
                              width: selected ? 3 : 1,
                            ),
                          ),
                          alignment: Alignment.center,
                          child: Text(
                            station.name.isNotEmpty ? station.name[0] : '?',
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
            RichAttributionWidget(
              attributions: [
                TextSourceAttribution(
                  kPrismaTileAttribution,
                  onTap: () => launchUrl(
                    Uri.parse('https://www.openstreetmap.org/copyright'),
                  ),
                ),
                TextSourceAttribution(
                  l10n.mapReportProblem,
                  onTap: () => launchUrl(
                    Uri.parse('https://www.openstreetmap.org/fixthemap'),
                  ),
                ),
              ],
            ),
          ],
        ),
        if (_tilesFailed)
          Positioned(
            top: 8,
            left: 8,
            right: 8,
            child: Material(
              color: theme.colorScheme.errorContainer,
              borderRadius: BorderRadius.circular(8),
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: Text(
                  l10n.mapTilesFailed,
                  style: TextStyle(color: theme.colorScheme.onErrorContainer),
                ),
              ),
            ),
          ),
        Positioned(
          bottom: 80,
          left: 8,
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(l10n.mapLegend, style: theme.textTheme.titleSmall),
                  for (final zone in zones)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            width: 12,
                            height: 12,
                            decoration: BoxDecoration(
                              color: zoneColors[zone],
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 6),
                          Text(zone),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(message, textAlign: TextAlign.center),
      ),
    );
  }
}
