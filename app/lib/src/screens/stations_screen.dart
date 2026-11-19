import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:material_ui/material_ui.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/models.dart';
import '../data/repository.dart';
import '../format.dart';
import '../l10n.dart';
import '../location_provider.dart';
import '../map_tiles.dart';
import '../nearest_station.dart';
import '../search_text.dart';
import '../station_bounds.dart';

/// Cap on the place results rendered for one query.
const int kMaxPlaceResults = 20;

class StationsScreen extends StatefulWidget {
  const StationsScreen({
    super.key,
    required this.latest,
    required this.onSelect,
    this.selectedId,
    this.tileProvider,
    this.repository,
    this.regionId,
    this.locationProvider,
  });

  final LatestDocument latest;
  final ValueChanged<String> onSelect;
  final String? selectedId;
  final TileProvider? tileProvider;
  final PrismaRepository? repository;
  final String? regionId;
  final LocationProvider? locationProvider;

  @override
  State<StationsScreen> createState() => _StationsScreenState();
}

class _StationsScreenState extends State<StationsScreen> {
  final TextEditingController _controller = TextEditingController();
  String _query = '';
  bool _mapView = false;
  String? _selectedMarkerId;
  bool _tilesFailed = false;
  bool _legendExpanded = false;
  bool _showTemperatures = true;
  String _selectedRegion = 'all';
  bool _showSatellite = false;
  int _satelliteFallbackDays = 0;
  bool _satelliteTilesFailed = false;

  PlaceDocument? _places;
  Future<void>? _placesLoading;
  bool _placesFailed = false;

  bool _locating = false;
  String? _locationError;
  GeoPoint? _userLocation;
  PlaceRecord? _selectedPlace;

  @override
  void initState() {
    super.initState();
    _loadView();
  }

  Future<void> _loadView() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final stored = prefs.getString('prisma_stations_view');
      final satStored = prefs.getBool('prisma_map_satellite_enabled');
      if (!mounted) return;
      setState(() {
        _mapView = stored == 'map';
        if (satStored != null) {
          _showSatellite = satStored;
        }
      });
    } catch (_) {}
  }

  Future<void> _setView(bool map) async {
    setState(() => _mapView = map);
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('prisma_stations_view', map ? 'map' : 'list');
    } catch (_) {}
  }

  Future<void> _toggleSatellite() async {
    final next = !_showSatellite;
    setState(() {
      _showSatellite = next;
      _satelliteFallbackDays = 0;
      _satelliteTilesFailed = false;
    });
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool('prisma_map_satellite_enabled', next);
    } catch (_) {}
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  static const Set<String> _kAmericas = {
    'la_quiaca', 'salta', 'tucuman', 'formosa', 'resistencia', 'posadas', 'mendoza',
    'san_juan', 'malargue', 'cordoba', 'rosario', 'buenos_aires', 'santa_rosa',
    'mar_del_plata', 'bahia_blanca', 'comodoro_rivadavia', 'bariloche', 'trelew', 'ushuaia',
    'santiago_pudahuel', 'punta_arenas', 'montevideo_carrasco', 'asuncion_pettirossi',
    'sao_paulo_congonhas', 'rio_janeiro_galeao', 'brasilia_aeroporto', 'manaus_eduardo_gomes',
    'lima_jorge_chavez', 'cusco_velasco_astete', 'bogota_el_dorado', 'quito_mariscal_sucre',
    'la_paz_el_alto', 'santa_cruz_viru_viru', 'buenos_aires_aeroparque', 'cordoba_aeropuerto',
    'bariloche_aeropuerto', 'new_york_jfk', 'chicago_ohare', 'miami_intl', 'houston_bush',
    'denver_intl', 'los_angeles_lax', 'seattle_tacoma', 'phoenix_sky_harbor', 'anchorage_intl',
    'toronto_pearson', 'halifax_stanfield', 'calgary_intl', 'vancouver_intl', 'yellowknife',
    'mexico_city_juarez', 'monterrey_intl', 'cancun_intl', 'guadalajara_intl',
  };

  static const Set<String> _kEurope = {
    'london_heathrow', 'paris_cdg', 'frankfurt_am_main', 'amsterdam_schiphol',
    'madrid_barajas', 'rome_fiumicino', 'athens_venizelos', 'lisbon_humberto_delgado',
    'vienna_schwechat', 'zurich_flughafen', 'stockholm_arlanda', 'helsinki_vantaa',
    'oslo_gardermoen', 'warsaw_chopin', 'prague_vaclav_havel', 'bucharest_otopeni',
    'reykjavik_keflavik', 'tromso_langnes',
  };

  static const Set<String> _kAsia = {
    'beijing_capital', 'shanghai_pudong', 'tokyo_haneda', 'seoul_incheon',
    'moscow_sheremetyevo', 'novosibirsk_tolmachevo', 'yakutsk_airport', 'delhi_indira_gandhi',
    'mumbai_chhatrapati', 'bangkok_suvarnabhumi', 'ho_chi_minh_tan_son_nhat',
    'singapore_changi', 'kuala_lumpur_intl', 'jakarta_soekarno_hatta', 'manila_ninoy_aquino',
    'taipei_taoyuan', 'almaty_intl', 'tashkent_islam_karimov', 'karachi_jinnah',
  };

  static const Set<String> _kAfrica = {
    'cairo_intl', 'casablanca_mohammed_v', 'dakar_blaise_diagne', 'lagos_murtala_muhammed',
    'accra_kotoka', 'nairobi_jomo_kenyatta', 'addis_ababa_bole', 'dar_es_salaam_julius_nyerere',
    'johannesburg_or_tambo', 'cape_town_intl', 'antananarivo_ivato', 'mauritius_ramgoolam',
    'kinshasa_ndjili', 'khartoum_intl', 'tunis_carthage', 'alger_houari_boumediene',
    'niamey_diori_hamani',
  };

  static const Set<String> _kOceania = {
    'sydney_kingsford_smith', 'melbourne_tullamarine', 'brisbane_airport', 'perth_airport',
    'adelaide_airport', 'darwin_intl', 'alice_springs', 'hobart_airport', 'cairns_airport',
    'auckland_airport', 'christchurch_intl', 'wellington_intl', 'nadi_intl',
    'port_moresby_jacksons', 'honolulu_daniel_k_inouye', 'papeete_faa_a',
  };

  static const Set<String> _kMiddleEast = {
    'dubai_intl', 'doha_hamad', 'riyadh_king_khalid', 'jeddah_king_abdulaziz',
    'kuwait_intl', 'bahrain_intl', 'muscat_intl', 'amman_queen_alia', 'beirut_rafic_hariri',
    'tel_aviv_ben_gurion', 'baghdad_intl', 'basra_intl', 'tehran_imam_khomeini',
    'shiraz_shahid_dastghaib', 'damascus_intl', 'erbil_intl',
  };

  List<StationSummary> get _filteredStations {
    final query = normalizeSearchText(_query.trim());
    return widget.latest.stations.where((station) {
      if (_selectedRegion != 'all') {
        final id = station.id;
        if (_selectedRegion == 'americas' && !_kAmericas.contains(id)) return false;
        if (_selectedRegion == 'europe' && !_kEurope.contains(id)) return false;
        if (_selectedRegion == 'asia' && !_kAsia.contains(id)) return false;
        if (_selectedRegion == 'africa' && !_kAfrica.contains(id)) return false;
        if (_selectedRegion == 'oceania' && !_kOceania.contains(id)) return false;
        if (_selectedRegion == 'middle_east' && !_kMiddleEast.contains(id)) return false;
      }
      if (query.isEmpty) return true;
      return normalizeSearchText(station.name).contains(query) ||
          normalizeSearchText(station.climateZone).contains(query) ||
          normalizeSearchText(station.id).contains(query);
    }).toList();
  }

  List<PlaceRecord> get _matchingPlaces {
    if (_query.trim().isEmpty) {
      return const <PlaceRecord>[];
    }
    final ranked = rankPlaces(_places?.places ?? const <PlaceRecord>[], _query);
    if (ranked.length <= kMaxPlaceResults) {
      return ranked;
    }
    return ranked.sublist(0, kMaxPlaceResults);
  }

  GeoPoint? get _selectedPoint {
    if (_userLocation != null) {
      return _userLocation;
    }
    final place = _selectedPlace;
    if (place == null) {
      return null;
    }
    return GeoPoint(lat: place.lat, lon: place.lon);
  }

  void _ensurePlaces() {
    if (_placesLoading != null || widget.repository == null) {
      return;
    }
    _placesLoading = _loadPlaces();
  }

  Future<void> _loadPlaces() async {
    final repository = widget.repository;
    if (repository == null) {
      return;
    }
    try {
      final index = await repository.loadPlaceIndex();
      final region = index.regionById(widget.regionId ?? '');
      if (region == null) {
        _placesLoading = null;
        if (mounted) {
          setState(() => _placesFailed = true);
        }
        return;
      }
      final document = await repository.loadPlaces(region.file);
      if (!mounted) {
        return;
      }
      setState(() {
        _places = document;
        _placesFailed = false;
      });
    } on Exception {
      _placesLoading = null;
      if (mounted) {
        setState(() => _placesFailed = true);
      }
    }
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

  Future<void> _openPlaceCard(PlaceRecord place) async {
    final nearest = nearestStation(
      GeoPoint(lat: place.lat, lon: place.lon),
      widget.latest.stations,
    );
    if (nearest == null) {
      return;
    }
    setState(() {
      _selectedPlace = place;
      _userLocation = null;
      _selectedMarkerId = nearest.station.id;
      _locationError = null;
    });
    await _showNearestCard(
      title: place.name,
      subtitle: place.admin1,
      nearest: nearest,
    );
    if (mounted) {
      setState(() => _selectedMarkerId = null);
    }
  }

  Future<void> _useMyLocation() async {
    final provider = widget.locationProvider ?? createLocationProvider();
    setState(() {
      _locating = true;
      _locationError = null;
    });
    try {
      final point = await provider.currentPosition();
      if (!mounted) {
        return;
      }
      final nearest = nearestStation(point, widget.latest.stations);
      if (nearest == null) {
        return;
      }
      setState(() {
        _userLocation = point;
        _selectedPlace = null;
        _selectedMarkerId = nearest.station.id;
      });
      await _showNearestCard(
        title: context.l10n.yourLocation,
        subtitle: '',
        nearest: nearest,
      );
    } on LocationException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() => _locationError = _locationMessage(context.l10n, error.kind));
    } on Exception {
      if (!mounted) {
        return;
      }
      setState(() => _locationError = context.l10n.locationUnavailable);
    } finally {
      if (mounted) {
        setState(() => _locating = false);
      }
    }
  }

  Future<void> _showNearestCard({
    required String title,
    required String subtitle,
    required NearestStation nearest,
  }) async {
    final width = MediaQuery.of(context).size.width;
    final l10n = context.l10n;
    final locale = context.localeTag;
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final card = Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: theme.textTheme.titleMedium),
          if (subtitle.trim().isNotEmpty) ...[
            const SizedBox(height: 2),
            Text(subtitle, style: theme.textTheme.bodySmall),
          ],
          const SizedBox(height: 12),
          Text(l10n.nearestStation(nearest.station.name)),
          const SizedBox(height: 4),
          Text(l10n.distanceKm(distanceValue(nearest.distanceKm, locale: locale))),
          if (nearest.distanceKm > kNearestStationWarningKm) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: scheme.errorContainer,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                l10n.nearestStationWarning,
                style: TextStyle(color: scheme.onErrorContainer),
              ),
            ),
          ],
          const SizedBox(height: 12),
          FilledButton(
            onPressed: () {
              Navigator.of(context).pop();
              widget.onSelect(nearest.station.id);
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
            onChanged: (value) {
              setState(() => _query = value);
              if (value.trim().isNotEmpty) {
                _ensurePlaces();
              }
            },
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
          child: Wrap(
            spacing: 8,
            runSpacing: 4,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              SegmentedButton<bool>(
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
              FilledButton.tonalIcon(
                onPressed: _locating ? null : _useMyLocation,
                icon: const Icon(Icons.my_location),
                label: Text(l10n.useMyLocation),
              ),
            ],
          ),
        ),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.fromLTRB(16, 2, 16, 6),
          child: Row(
            children: [
              for (final entry in const [
                ('all', 'All (140)'),
                ('americas', 'Americas (54)'),
                ('europe', 'Europe (18)'),
                ('asia', 'Asia (19)'),
                ('africa', 'Africa (17)'),
                ('oceania', 'Oceania (16)'),
                ('middle_east', 'Middle East (16)'),
              ])
                Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: FilterChip(
                    visualDensity: VisualDensity.compact,
                    selected: _selectedRegion == entry.$1,
                    label: Text(entry.$2),
                    onSelected: (selected) {
                      setState(() {
                        _selectedRegion = selected ? entry.$1 : 'all';
                      });
                    },
                  ),
                ),
            ],
          ),
        ),
        if (_locationError != null)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 4),
            child: Material(
              color: theme.colorScheme.errorContainer,
              borderRadius: BorderRadius.circular(8),
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: Row(
                  children: [
                    Icon(
                      Icons.location_off,
                      color: theme.colorScheme.onErrorContainer,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        _locationError!,
                        style: TextStyle(
                          color: theme.colorScheme.onErrorContainer,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        Expanded(
          child: _mapView
              ? _buildMap(context, filtered, zones, zoneColors, l10n, theme)
              : _buildResults(context, filtered, l10n, theme),
        ),
      ],
    );
  }

  Widget _buildResults(
    BuildContext context,
    List<StationSummary> stations,
    AppLocalizations l10n,
    ThemeData theme,
  ) {
    final places = _matchingPlaces;
    final searching = _query.trim().isNotEmpty;
    if (stations.isEmpty && places.isEmpty) {
      final message = searching && _placesFailed
          ? l10n.placesUnavailable
          : l10n.searchNoResults;
      return EmptyState(message: message);
    }
    final tiles = <Widget>[];
    if (stations.isNotEmpty) {
      if (searching) {
        tiles.add(_sectionHeader(theme, l10n.searchStationsGroup));
      }
      for (final station in stations) {
        final selected = station.id == widget.selectedId;
        tiles.add(
          ListTile(
            selected: selected,
            title: Text(station.name),
            subtitle: Text(
              '${station.climateZone} · ${coordinates(station.lat, station.lon, locale: context.localeTag)}',
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => widget.onSelect(station.id),
          ),
        );
      }
    }
    if (places.isNotEmpty) {
      tiles.add(_sectionHeader(theme, l10n.searchPlacesGroup));
      for (final place in places) {
        tiles.add(
          ListTile(
            leading: const Icon(Icons.place_outlined),
            title: Text(place.name),
            subtitle: Text(place.admin1),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _openPlaceCard(place),
          ),
        );
      }
    }
    if (searching && _placesFailed) {
      tiles.add(
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
          child: Text(
            l10n.placesUnavailable,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ),
      );
    }
    return ListView(
      padding: const EdgeInsets.fromLTRB(8, 4, 8, 16),
      children: tiles,
    );
  }

  Widget _sectionHeader(ThemeData theme, String label) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      child: Text(
        label,
        style: theme.textTheme.titleSmall?.copyWith(
          color: theme.colorScheme.primary,
        ),
      ),
    );
  }

  Widget _buildMap(
    BuildContext context,
    List<StationSummary> filtered,
    List<String> zones,
    Map<String, Color> zoneColors,
    AppLocalizations l10n,
    ThemeData theme,
  ) {
    final allBounds = computeStationBounds(widget.latest.stations);
    final cameraFit = allBounds != null
        ? CameraFit.bounds(
            bounds: allBounds,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
          )
        : null;
    final point = _selectedPoint;
    final nearest = point == null
        ? null
        : nearestStation(point, widget.latest.stations);
    final mapStations = <StationSummary>[...filtered];
    if (nearest != null && !mapStations.any((s) => s.id == nearest.station.id)) {
      mapStations.add(nearest.station);
    }

    return Stack(
      children: [
        FlutterMap(
          options: MapOptions(
            initialCameraFit: cameraFit,
            interactionOptions: const InteractionOptions(
              flags: InteractiveFlag.all & ~InteractiveFlag.rotate,
            ),
            minZoom: 1.2,
            maxZoom: 10,
          ),
          children: [
            if (_showSatellite && !_satelliteTilesFailed)
              TileLayer(
                key: ValueKey(
                  'gibs_tile_layer_${resolveGibsDate(null, _satelliteFallbackDays)}',
                ),
                urlTemplate: buildGibsTileUrlTemplate(
                  extraDaysBack: _satelliteFallbackDays,
                ),
                tileProvider: widget.tileProvider ?? NetworkTileProvider(),
                userAgentPackageName: kPrismaTileUserAgent,
                maxNativeZoom: kPrismaGibsMaxNativeZoom,
                maxZoom: 10,
                errorTileCallback: (tile, error, stackTrace) {
                  if (!mounted) return;
                  if (_satelliteFallbackDays < kPrismaGibsMaxFallbackDays) {
                    setState(() => _satelliteFallbackDays++);
                  } else if (!_satelliteTilesFailed) {
                    setState(() => _satelliteTilesFailed = true);
                  }
                },
              )
            else
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
            if (point != null && nearest != null)
              PolylineLayer(
                polylines: [
                  Polyline(
                    points: [
                      LatLng(point.lat, point.lon),
                      LatLng(nearest.station.lat, nearest.station.lon),
                    ],
                    strokeWidth: 2,
                    color: theme.colorScheme.primary,
                  ),
                ],
              ),
            MarkerLayer(
              markers: mapStations.map((station) {
                final selected = station.id == _selectedMarkerId;
                final hasTemp = _showTemperatures && station.t2mMax != null;
                final width = hasTemp ? (selected ? 60.0 : 52.0) : (selected ? 26.0 : 18.0);
                final height = hasTemp ? (selected ? 28.0 : 24.0) : (selected ? 26.0 : 18.0);
                return Marker(
                  point: LatLng(station.lat, station.lon),
                  width: width,
                  height: height,
                  child: Semantics(
                    label: hasTemp
                        ? '${station.name}: ${station.t2mMax!.round()}°'
                        : station.name,
                    button: true,
                    child: GestureDetector(
                      onTap: () => _openCard(station),
                      child: Tooltip(
                        message: hasTemp
                            ? '${station.name} (${station.t2mMax!.round()}°)'
                            : station.name,
                        child: hasTemp
                            ? Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 3,
                                  vertical: 1,
                                ),
                                decoration: BoxDecoration(
                                  color: theme.colorScheme.surface,
                                  borderRadius: BorderRadius.circular(12),
                                  border: Border.all(
                                    color: selected
                                        ? theme.colorScheme.primary
                                        : (zoneColors[station.climateZone] ??
                                            Colors.black87),
                                    width: selected ? 2.2 : 1.2,
                                  ),
                                  boxShadow: [
                                    BoxShadow(
                                      color: Colors.black.withValues(
                                        alpha: selected ? 0.4 : 0.2,
                                      ),
                                      blurRadius: selected ? 4 : 2,
                                      offset: const Offset(0, 1),
                                    ),
                                  ],
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Container(
                                      width: 6,
                                      height: 6,
                                      decoration: BoxDecoration(
                                        color: zoneColors[station.climateZone],
                                        shape: BoxShape.circle,
                                      ),
                                    ),
                                    const SizedBox(width: 2),
                                    Flexible(
                                      child: Text(
                                        '${station.t2mMax!.round()}°',
                                        maxLines: 1,
                                        overflow: TextOverflow.clip,
                                        style: TextStyle(
                                          fontSize: selected ? 11 : 10,
                                          fontWeight: FontWeight.bold,
                                          color: theme.colorScheme.onSurface,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              )
                            : Container(
                                decoration: BoxDecoration(
                                  color: zoneColors[station.climateZone],
                                  shape: BoxShape.circle,
                                  border: Border.all(
                                    color: selected ? Colors.white : Colors.black87,
                                    width: selected ? 2.5 : 1.2,
                                  ),
                                  boxShadow: [
                                    BoxShadow(
                                      color: Colors.black.withValues(
                                        alpha: selected ? 0.4 : 0.2,
                                      ),
                                      blurRadius: selected ? 4 : 2,
                                      offset: const Offset(0, 1),
                                    ),
                                  ],
                                ),
                              ),
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
            if (point != null)
              MarkerLayer(
                markers: [
                  Marker(
                    point: LatLng(point.lat, point.lon),
                    width: 44,
                    height: 44,
                    child: Tooltip(
                      message: _userLocation != null
                          ? l10n.yourLocation
                          : (_selectedPlace?.name ?? ''),
                      child: Icon(
                        _userLocation != null
                            ? Icons.my_location
                            : Icons.place,
                        color: theme.colorScheme.primary,
                        size: 34,
                      ),
                    ),
                  ),
                ],
              ),
            RichAttributionWidget(
              attributions: [
                if (_showSatellite && !_satelliteTilesFailed)
                  TextSourceAttribution(
                    kPrismaGibsAttribution,
                    onTap: () => launchUrl(
                      Uri.parse(kPrismaGibsAttributionUrl),
                    ),
                  )
                else ...[
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
          bottom: 24,
          left: 8,
          child: _legendExpanded
              ? Card(
                  elevation: 4,
                  child: Container(
                    constraints: const BoxConstraints(maxHeight: 260, maxWidth: 320),
                    padding: const EdgeInsets.all(10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(l10n.mapLegend, style: theme.textTheme.titleSmall),
                            const SizedBox(width: 8),
                            InkWell(
                              borderRadius: BorderRadius.circular(12),
                              onTap: () => setState(() => _legendExpanded = false),
                              child: const Padding(
                                padding: EdgeInsets.all(2),
                                child: Icon(Icons.expand_more, size: 20),
                              ),
                            ),
                          ],
                        ),
                        const Divider(height: 12),
                        Flexible(
                          child: SingleChildScrollView(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                for (final zone in zones)
                                  Padding(
                                    padding: const EdgeInsets.only(bottom: 4),
                                    child: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Container(
                                          width: 10,
                                          height: 10,
                                          decoration: BoxDecoration(
                                            color: zoneColors[zone],
                                            shape: BoxShape.circle,
                                          ),
                                        ),
                                        const SizedBox(width: 6),
                                        Flexible(
                                          child: Text(
                                            zone,
                                            style: theme.textTheme.bodySmall,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                )
              : Card(
                  elevation: 2,
                  child: InkWell(
                    borderRadius: BorderRadius.circular(8),
                    onTap: () => setState(() => _legendExpanded = true),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.palette_outlined,
                            size: 16,
                            color: theme.colorScheme.primary,
                          ),
                          const SizedBox(width: 6),
                          Text(
                            l10n.mapLegend,
                            style: theme.textTheme.labelMedium?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(width: 4),
                          const Icon(Icons.expand_less, size: 18),
                        ],
                      ),
                    ),
                  ),
                ),
        ),
        Positioned(
          top: 8,
          right: 8,
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Card(
                elevation: 2,
                child: InkWell(
                  key: const ValueKey('map_satellite_toggle'),
                  borderRadius: BorderRadius.circular(8),
                  onTap: _toggleSatellite,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 6,
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.satellite_alt,
                          size: 16,
                          color: _showSatellite
                              ? theme.colorScheme.primary
                              : theme.colorScheme.onSurfaceVariant,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          'SAT',
                          style: theme.textTheme.labelMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: _showSatellite
                                ? theme.colorScheme.primary
                                : theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              if (mapStations.any((s) => s.t2mMax != null)) ...[
                const SizedBox(width: 6),
                Card(
                  elevation: 2,
                  child: InkWell(
                    key: const ValueKey('map_temp_toggle'),
                    borderRadius: BorderRadius.circular(8),
                    onTap: () => setState(
                      () => _showTemperatures = !_showTemperatures,
                    ),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 6,
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            _showTemperatures
                                ? Icons.thermostat
                                : Icons.thermostat_outlined,
                            size: 16,
                            color: _showTemperatures
                                ? theme.colorScheme.primary
                                : theme.colorScheme.onSurfaceVariant,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            '°C',
                            style: theme.textTheme.labelMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: _showTemperatures
                                  ? theme.colorScheme.primary
                                  : theme.colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    );
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
          if (station.t2mMax != null) ...[
            const SizedBox(height: 6),
            Text(
              station.t2mMin != null
                  ? '${l10n.variableT2mMax}: ${station.t2mMax!.round()}°C · ${l10n.variableT2mMin}: ${station.t2mMin!.round()}°C'
                  : '${l10n.variableT2mMax}: ${station.t2mMax!.round()}°C',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ],
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
}

String _locationMessage(AppLocalizations l10n, LocationErrorKind kind) {
  return switch (kind) {
    LocationErrorKind.denied => l10n.locationDenied,
    LocationErrorKind.unavailable => l10n.locationUnavailable,
    LocationErrorKind.timeout => l10n.locationTimeout,
  };
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
