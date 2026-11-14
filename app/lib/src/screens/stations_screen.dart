import 'package:material_ui/material_ui.dart';

import '../data/models.dart';
import '../format.dart';
import '../strings.dart';

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
  });

  final LatestDocument latest;
  final ValueChanged<String> onSelect;
  final String? selectedId;

  @override
  State<StationsScreen> createState() => _StationsScreenState();
}

class _StationsScreenState extends State<StationsScreen> {
  final TextEditingController _controller = TextEditingController();
  String _query = '';

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final query = _normalize(_query.trim());
    final stations = widget.latest.stations.where((station) {
      if (query.isEmpty) {
        return true;
      }
      return _normalize(station.name).contains(query) ||
          _normalize(station.climateZone).contains(query) ||
          _normalize(station.id).contains(query);
    }).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  S.stationCount(widget.latest.stations.length),
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
              hintText: S.searchHint,
              prefixIcon: const Icon(Icons.search),
              isDense: true,
              border: const OutlineInputBorder(),
              suffixIcon: _query.isEmpty
                  ? null
                  : IconButton(
                      tooltip: S.clearSearch,
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
            S.stationsIntro,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        Expanded(
          child: stations.isEmpty
              ? const EmptyState(message: S.searchNoResults)
              : ListView.separated(
                  padding: const EdgeInsets.fromLTRB(8, 4, 8, 16),
                  itemCount: stations.length,
                  separatorBuilder: (_, _) => const Divider(height: 1),
                  itemBuilder: (context, index) {
                    final station = stations[index];
                    final selected = station.id == widget.selectedId;
                    return ListTile(
                      selected: selected,
                      title: Text(station.name),
                      subtitle: Text(
                        '${station.climateZone} · ${coordinates(station.lat, station.lon)}',
                      ),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => widget.onSelect(station.id),
                    );
                  },
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
