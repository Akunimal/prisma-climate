import 'package:intl/intl.dart';
import 'package:material_ui/material_ui.dart';

import '../data/models.dart';
import '../data/repository.dart';
import '../format.dart';
import '../l10n.dart';
import '../widgets/common.dart';

class SkillScreen extends StatefulWidget {
  const SkillScreen({super.key, required this.repository});

  final PrismaRepository repository;

  @override
  State<SkillScreen> createState() => _SkillScreenState();
}

class _SkillScreenState extends State<SkillScreen> {
  late Future<SkillDocument> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.repository.loadSkill();
  }

  void _reload() {
    setState(() => _future = widget.repository.loadSkill());
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<SkillDocument>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const LoadingView();
        }
        if (snapshot.hasError) {
          return ErrorView(
            title: context.l10n.errorTitle('skill.json'),
            message: describeError(context, snapshot.error!),
            onRetry: _reload,
          );
        }
        return _SkillBody(document: snapshot.data!);
      },
    );
  }
}

class _SkillBody extends StatelessWidget {
  const _SkillBody({required this.document});

  final SkillDocument document;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = context.l10n;
    final locale = context.localeTag;
    final gate = document.gate;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: theme.colorScheme.tertiaryContainer,
            borderRadius: BorderRadius.circular(10),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.history_toggle_off, size: 18, color: theme.colorScheme.tertiary),
              const SizedBox(width: 8),
              Expanded(child: Text(l10n.skillHindcastBanner, style: theme.textTheme.bodySmall)),
            ],
          ),
        ),
        const SizedBox(height: 14),
        SectionCard(
          title: l10n.skillTitle,
          subtitle: '${l10n.skillLabel}: ${document.label}',
          child: !document.available
              ? EmptyNote(message: document.message ?? l10n.skillUnavailable)
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Wrap(
                      spacing: 16,
                      runSpacing: 8,
                      children: [
                        _MetricChip(
                          label: l10n.skillMeanEmos,
                          value: _crpss(document.meanCrpssEmos, locale: locale),
                          negative: (document.meanCrpssEmos ?? 0) <= 0,
                        ),
                        _MetricChip(
                          label: l10n.skillMeanQm,
                          value: _crpss(document.meanCrpssQm, locale: locale),
                          negative: (document.meanCrpssQm ?? 0) <= 0,
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(
                      l10n.skillCellsCount(
                        document.nSufficient ?? 0,
                        document.nCells ?? 0,
                      ),
                      style: theme.textTheme.bodySmall,
                    ),
                    if ((document.meanCrpssEmos ?? 0) <= 0) ...[
                      const SizedBox(height: 6),
                      Text(
                        l10n.skillDidNotBeat,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.error,
                        ),
                      ),
                    ],
                    const SizedBox(height: 10),
                    _MetaRow(label: l10n.skillProvider, value: document.provider ?? '—'),
                    _MetaRow(
                      label: l10n.skillWindow,
                      value: document.windowStart == null
                          ? '—'
                          : '${document.windowStart} → ${document.windowEnd ?? '—'}',
                    ),
                    _MetaRow(
                      label: l10n.skillRetrieved,
                      value: document.retrievedAt == null
                          ? '—'
                          : argentinaDateTime(document.retrievedAt!, locale: locale),
                    ),
                    _MetaRow(
                      label: l10n.skillLeads,
                      value: document.leads == null || document.leads!.isEmpty
                          ? '—'
                          : document.leads!.map((lead) => l10n.leadDay(lead)).join(', '),
                    ),
                    _MetaRow(label: l10n.skillMode, value: document.mode ?? '—'),
                  ],
                ),
        ),
        SectionCard(
          title: l10n.skillGateTitle,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                l10n.skillGateArchived(gate.archivedIssueDates, gate.requiredIssueDates),
                style: theme.textTheme.bodySmall,
              ),
              const SizedBox(height: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                decoration: BoxDecoration(
                  color: gate.open
                      ? theme.colorScheme.primaryContainer
                      : theme.colorScheme.errorContainer.withValues(alpha: 0.45),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      gate.open ? Icons.check_circle_outline : Icons.lock_outline,
                      size: 18,
                      color: gate.open
                          ? theme.colorScheme.onPrimaryContainer
                          : theme.colorScheme.onErrorContainer,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        gate.open ? l10n.skillGateOpen : l10n.skillGateClosed,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: gate.open
                              ? theme.colorScheme.onPrimaryContainer
                              : theme.colorScheme.onErrorContainer,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 8),
              Text(
                gate.note,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
        if (document.cells.isNotEmpty)
          SectionCard(
            title: l10n.skillCellsTitle,
            subtitle: l10n.legendModelsNeverPooled,
            child: _CellsTable(cells: document.cells),
          ),
        if (document.note != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              document.note!,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
      ],
    );
  }
}

String _crpss(double? value, {String? locale}) {
  if (value == null) {
    return '—';
  }
  return NumberFormat('0.0000', locale).format(value);
}

class _MetricChip extends StatelessWidget {
  const _MetricChip({
    required this.label,
    required this.value,
    required this.negative,
  });

  final String label;
  final String value;
  final bool negative;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: negative
            ? theme.colorScheme.errorContainer.withValues(alpha: 0.45)
            : theme.colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: theme.textTheme.labelSmall?.copyWith(
              color: negative
                  ? theme.colorScheme.onErrorContainer
                  : theme.colorScheme.onPrimaryContainer,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: theme.textTheme.titleMedium?.copyWith(
              color: negative
                  ? theme.colorScheme.onErrorContainer
                  : theme.colorScheme.onPrimaryContainer,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
        ],
      ),
    );
  }
}

class _MetaRow extends StatelessWidget {
  const _MetaRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 130,
            child: Text(
              label,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          Expanded(child: Text(value, style: theme.textTheme.bodySmall)),
        ],
      ),
    );
  }
}

class _CellsTable extends StatelessWidget {
  const _CellsTable({required this.cells});

  final List<SkillCell> cells;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = context.l10n;
    final locale = context.localeTag;
    final header = theme.textTheme.labelSmall?.copyWith(
      color: theme.colorScheme.onSurfaceVariant,
    );
    final sorted = [...cells]
      ..sort((a, b) {
        final byStation = a.station.compareTo(b.station);
        return byStation != 0 ? byStation : a.leadDay.compareTo(b.leadDay);
      });
    return Column(
      children: [
        Row(
          children: [
            Expanded(child: Text(l10n.skillCellStation, style: header)),
            SizedBox(width: 56, child: Text(l10n.legendLeadAxis, style: header)),
            SizedBox(
              width: 72,
              child: Text('EMOS', style: header, textAlign: TextAlign.right),
            ),
            SizedBox(
              width: 72,
              child: Text('QM', style: header, textAlign: TextAlign.right),
            ),
          ],
        ),
        const Divider(height: 10),
        for (final cell in sorted)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 3),
            child: Row(
              children: [
                Expanded(
                  child: Text(cell.station, style: theme.textTheme.bodySmall),
                ),
                SizedBox(
                  width: 56,
                  child: Text(
                    l10n.leadDay(cell.leadDay),
                    style: theme.textTheme.bodySmall,
                  ),
                ),
                SizedBox(
                  width: 72,
                  child: Text(
                    cell.insufficient ? '—' : _crpss(cell.crpssEmos, locale: locale),
                    textAlign: TextAlign.right,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: !cell.insufficient && (cell.crpssEmos ?? 0) < 0
                          ? theme.colorScheme.error
                          : null,
                    ),
                  ),
                ),
                SizedBox(
                  width: 72,
                  child: Text(
                    cell.insufficient ? '—' : _crpss(cell.crpssQm, locale: locale),
                    textAlign: TextAlign.right,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: !cell.insufficient && (cell.crpssQm ?? 0) < 0
                          ? theme.colorScheme.error
                          : null,
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}
