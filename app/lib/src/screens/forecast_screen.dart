import 'package:material_ui/material_ui.dart';

import '../data/models.dart';
import '../data/repository.dart';
import '../format.dart';
import '../l10n.dart';
import '../model_labels.dart';
import '../widgets/band_chart.dart';
import '../widgets/common.dart';

class ForecastScreen extends StatefulWidget {
  const ForecastScreen({
    super.key,
    required this.repository,
    required this.latest,
    required this.about,
    required this.stationId,
    required this.onStationChanged,
  });

  final PrismaRepository repository;
  final LatestDocument latest;
  final AboutDocument about;
  final String stationId;
  final ValueChanged<String> onStationChanged;

  @override
  State<ForecastScreen> createState() => _ForecastScreenState();
}

class _ForecastScreenState extends State<ForecastScreen> {
  late Future<StationDocument> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.repository.loadStation(widget.stationId);
  }

  @override
  void didUpdateWidget(covariant ForecastScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.stationId != widget.stationId ||
        oldWidget.repository != widget.repository) {
      _future = widget.repository.loadStation(widget.stationId);
    }
  }

  void _reload() {
    setState(() => _future = widget.repository.loadStation(widget.stationId));
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<StationDocument>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const LoadingView();
        }
        if (snapshot.hasError) {
          return ErrorView(
            title: context.l10n.errorTitle('stations/${widget.stationId}.json'),
            message: describeError(context, snapshot.error!),
            onRetry: _reload,
          );
        }
        return _ForecastBody(
          document: snapshot.data!,
          latest: widget.latest,
          about: widget.about,
          onStationChanged: widget.onStationChanged,
        );
      },
    );
  }
}

class _ForecastBody extends StatelessWidget {
  const _ForecastBody({
    required this.document,
    required this.latest,
    required this.about,
    required this.onStationChanged,
  });

  final StationDocument document;
  final LatestDocument latest;
  final AboutDocument about;
  final ValueChanged<String> onStationChanged;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = context.l10n;
    final locale = context.localeTag;
    final station = document.station;
    final modelNames = document.models.map(modelLabel).join(' · ');

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 380),
              child: DropdownButton<String>(
                value: station.id,
                isExpanded: true,
                items: [
                  for (final item in latest.stations)
                    DropdownMenuItem(value: item.id, child: Text(item.name)),
                ],
                onChanged: (value) {
                  if (value != null) {
                    onStationChanged(value);
                  }
                },
              ),
            ),
            Text(
              '${station.climateZone} · ${coordinates(station.lat, station.lon, locale: locale)}',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        Text(
          '${l10n.labelIssue}: ${argentinaDateTime(document.issueTime, locale: locale)} ${l10n.argentinaTimeNote}',
          style: theme.textTheme.bodySmall,
        ),
        Padding(
          padding: const EdgeInsets.only(top: 2),
          child: Text(
            '${l10n.labelSmn}: ${about.smnSnapshotDate ?? '—'}',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        const SizedBox(height: 12),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: theme.colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(10),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.info_outline, size: 18, color: theme.colorScheme.primary),
              const SizedBox(width: 8),
              Expanded(child: Text(l10n.rawBanner, style: theme.textTheme.bodySmall)),
            ],
          ),
        ),
        const SizedBox(height: 14),
        _VariableCard(
          document: document,
          variable: 't2m_max',
          title: l10n.variableT2mMax,
          subtitle: modelNames,
        ),
        _VariableCard(
          document: document,
          variable: 't2m_min',
          title: l10n.variableT2mMin,
          subtitle: modelNames,
        ),
        _PrecipCard(document: document),
        _ObservedCard(document: document),
        Card(
          margin: const EdgeInsets.only(bottom: 14),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
            child: AttributionBar(about: about),
          ),
        ),
      ],
    );
  }
}

Widget _chartFrame(Widget child) {
  return LayoutBuilder(
    builder: (context, constraints) {
      if (constraints.maxWidth >= 560) {
        return SizedBox(height: 240, width: constraints.maxWidth, child: child);
      }
      return SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: SizedBox(height: 240, width: 560, child: child),
      );
    },
  );
}

List<String> _missingNotes(
  BuildContext context,
  StationDocument document,
  String variable,
) {
  final l10n = context.l10n;
  final notes = <String>[];
  for (final model in document.models) {
    for (final item in document.casesFor(variable, model)) {
      if (item.isMissing) {
        notes.add(
          '${modelLabel(model)} · ${l10n.leadDay(item.leadDay)}: '
          '${l10n.missingMembers(item.nMembers, item.nominalMembers)}',
        );
      }
    }
  }
  return notes;
}

class _VariableCard extends StatelessWidget {
  const _VariableCard({
    required this.document,
    required this.variable,
    required this.title,
    required this.subtitle,
  });

  final StationDocument document;
  final String variable;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = context.l10n;
    final locale = context.localeTag;
    final leads = document.leadDays;
    final dateForLead = <int, String>{};
    final series = <BandSeries>[];
    for (final model in document.models) {
      final cases = document.casesFor(variable, model);
      for (final item in cases) {
        dateForLead[item.leadDay] = dayMonth(item.validLocalDate, locale: locale);
      }
      series.add(
        BandSeries(
          label: modelLabel(model),
          color: modelColor(context, model),
          cases: cases,
        ),
      );
    }
    final missing = _missingNotes(context, document, variable);

    return SectionCard(
      title: title,
      subtitle: subtitle,
      child: series.isEmpty || leads.isEmpty
          ? EmptyNote(message: l10n.noData)
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 16,
                  runSpacing: 6,
                  children: [
                    for (final item in series)
                      LegendDot(color: item.color, label: item.label),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  '${l10n.legendBand1090} · ${l10n.legendBand2575} · ${l10n.legendMedian}',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 6),
                _chartFrame(
                  ForecastBandChart(
                    leads: leads,
                    series: series,
                    dateForLead: dateForLead,
                    noDataLabel: l10n.noData,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  l10n.legendModelsNeverPooled,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                if (missing.isNotEmpty) _MissingBox(lines: missing),
              ],
            ),
    );
  }
}

class _MissingBox extends StatelessWidget {
  const _MissingBox({required this.lines});

  final List<String> lines;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: theme.colorScheme.errorContainer.withValues(alpha: 0.45),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            context.l10n.missingMembersTitle,
            style: theme.textTheme.labelLarge?.copyWith(
              color: theme.colorScheme.onErrorContainer,
            ),
          ),
          for (final line in lines)
            Text(
              line,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onErrorContainer,
              ),
            ),
        ],
      ),
    );
  }
}

class _PrecipCard extends StatelessWidget {
  const _PrecipCard({required this.document});

  final StationDocument document;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = context.l10n;
    final models = document.models
        .where((model) => document.casesFor('precip', model).isNotEmpty)
        .toList();
    if (models.isEmpty) {
      return SectionCard(
        title: l10n.precipTitle,
        child: EmptyNote(message: l10n.noData),
      );
    }
    return SectionCard(
      title: l10n.precipTitle,
      subtitle: l10n.precipNote,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final model in models) ...[
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: LegendDot(
                color: modelColor(context, model),
                label: modelLabel(model),
              ),
            ),
            _PrecipTable(cases: document.casesFor('precip', model)),
            const SizedBox(height: 14),
          ],
          Text(
            l10n.legendModelsNeverPooled,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}

class _PrecipTable extends StatelessWidget {
  const _PrecipTable({required this.cases});

  final List<ForecastCase> cases;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = context.l10n;
    final locale = context.localeTag;
    final header = theme.textTheme.labelSmall?.copyWith(
      color: theme.colorScheme.onSurfaceVariant,
    );
    return Column(
      children: [
        Row(
          children: [
            SizedBox(width: 40, child: Text(l10n.day, style: header)),
            SizedBox(width: 62, child: Text(l10n.date, style: header)),
            Expanded(child: Text(l10n.precipGe1, style: header, textAlign: TextAlign.right)),
            Expanded(child: Text(l10n.precipGe10, style: header, textAlign: TextAlign.right)),
          ],
        ),
        const Divider(height: 10),
        for (final item in cases)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 3),
            child: Row(
              children: [
                SizedBox(
                  width: 40,
                  child: Text(l10n.leadDay(item.leadDay), style: theme.textTheme.bodySmall),
                ),
                SizedBox(
                  width: 62,
                  child: Text(
                    dayMonth(item.validLocalDate, locale: locale),
                    style: theme.textTheme.bodySmall,
                  ),
                ),
                if (item.isMissing)
                  Expanded(
                    flex: 2,
                    child: Text(
                      l10n.missingMembers(item.nMembers, item.nominalMembers),
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.error,
                      ),
                    ),
                  )
                else ...[
                  Expanded(
                    child: Text(
                      percent(item.fractionGe1mm, locale: locale),
                      textAlign: TextAlign.right,
                      style: theme.textTheme.bodySmall,
                    ),
                  ),
                  Expanded(
                    child: Text(
                      percent(item.fractionGe10mm, locale: locale),
                      textAlign: TextAlign.right,
                      style: theme.textTheme.bodySmall,
                    ),
                  ),
                ],
              ],
            ),
          ),
      ],
    );
  }
}

class _ObservedCard extends StatelessWidget {
  const _ObservedCard({required this.document});

  final StationDocument document;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = context.l10n;
    final locale = context.localeTag;
    final days = document.observed;
    if (days.isEmpty) {
      return SectionCard(
        title: l10n.observedTitle,
        subtitle: l10n.observedNote,
        child: EmptyNote(message: l10n.noData),
      );
    }
    return SectionCard(
      title: l10n.observedTitle,
      subtitle: l10n.observedNote,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 16,
            runSpacing: 6,
            children: [
              LegendDot(color: theme.colorScheme.error, label: l10n.observedMax),
              LegendDot(color: theme.colorScheme.primary, label: l10n.observedMin),
            ],
          ),
          const SizedBox(height: 6),
          _chartFrame(
            ObservedChart(
              days: days,
              dateLabel: (isoDate) => dayMonth(isoDate, locale: locale),
            ),
          ),
          const SizedBox(height: 8),
          Container(
            height: 220,
            decoration: BoxDecoration(
              border: Border.all(color: theme.colorScheme.outlineVariant),
              borderRadius: BorderRadius.circular(8),
            ),
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              itemCount: days.length,
              itemBuilder: (context, index) {
                final day = days[index];
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          dayMonthYear(day.date, locale: locale),
                          style: theme.textTheme.bodySmall,
                        ),
                      ),
                      SizedBox(
                        width: 64,
                        child: Text(
                          degrees(day.t2mMax, locale: locale),
                          textAlign: TextAlign.right,
                          style: theme.textTheme.bodySmall,
                        ),
                      ),
                      SizedBox(
                        width: 64,
                        child: Text(
                          degrees(day.t2mMin, locale: locale),
                          textAlign: TextAlign.right,
                          style: theme.textTheme.bodySmall,
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
