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

class _SkillPayload {
  const _SkillPayload({required this.skill, this.leaderboard});

  final SkillDocument skill;
  final LeaderboardDocument? leaderboard;
}

class _SkillScreenState extends State<SkillScreen> {
  late Future<_SkillPayload> _future;

  @override
  void initState() {
    super.initState();
    _future = _fetch();
  }

  Future<_SkillPayload> _fetch() async {
    final skill = await widget.repository.loadSkill();
    LeaderboardDocument? leaderboard;
    try {
      leaderboard = await widget.repository.loadLeaderboard();
    } catch (_) {
      // Graceful degradation when leaderboard.json is absent
    }
    return _SkillPayload(skill: skill, leaderboard: leaderboard);
  }

  void _reload() {
    setState(() => _future = _fetch());
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_SkillPayload>(
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
        return _SkillBody(
          document: snapshot.data!.skill,
          leaderboard: snapshot.data!.leaderboard,
        );
      },
    );
  }
}

class _SkillBody extends StatelessWidget {
  const _SkillBody({required this.document, this.leaderboard});

  final SkillDocument document;
  final LeaderboardDocument? leaderboard;

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
        if (leaderboard != null)
          _OperationalLeaderboardCard(leaderboard: leaderboard!),
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

class _OperationalLeaderboardCard extends StatelessWidget {
  const _OperationalLeaderboardCard({required this.leaderboard});

  final LeaderboardDocument leaderboard;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final locale = context.localeTag;
    final gate = leaderboard.gate;

    if (gate.isLocked) {
      final archived = gate.archivedIssueDates;
      final required = gate.requiredIssueDates;
      final remaining = gate.remainingIssueDates;
      final progress = required > 0 ? (archived / required).clamp(0.0, 1.0) : 0.0;

      return SectionCard(
        title: 'Operational verification leaderboard',
        subtitle: 'Raw ensemble vs Climatology vs Persistence · docs/EVALUATION_PROTOCOL.md',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Archived issue dates: $archived of $required ($remaining remaining)',
              style: theme.textTheme.bodySmall,
            ),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: progress,
                minHeight: 6,
                backgroundColor: theme.colorScheme.surfaceContainerHighest,
                valueColor: AlwaysStoppedAnimation<Color>(theme.colorScheme.primary),
              ),
            ),
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.lock_outline, size: 18, color: theme.colorScheme.primary),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      gate.note,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    }

    final summary = leaderboard.summary;
    return SectionCard(
      title: 'Operational verification leaderboard',
      subtitle: 'Raw ensemble vs Climatology vs Persistence',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (summary != null) ...[
            Wrap(
              spacing: 16,
              runSpacing: 8,
              children: [
                _MetricChip(
                  label: 'Mean CRPSS (vs Climatology)',
                  value: _crpss(summary.meanCrpssVsClimatology, locale: locale),
                  negative: (summary.meanCrpssVsClimatology ?? 0) <= 0,
                ),
                _MetricChip(
                  label: 'Mean CRPSS (vs Persistence)',
                  value: _crpss(summary.meanCrpssVsPersistence, locale: locale),
                  negative: (summary.meanCrpssVsPersistence ?? 0) <= 0,
                ),
              ],
            ),
            const SizedBox(height: 10),
          ],
          if (leaderboard.cells.isNotEmpty)
            _LeaderboardTable(cells: leaderboard.cells),
        ],
      ),
    );
  }
}

class _LeaderboardTable extends StatelessWidget {
  const _LeaderboardTable({required this.cells});

  final List<LeaderboardCell> cells;

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
        final byStation = a.location.compareTo(b.location);
        if (byStation != 0) return byStation;
        final byModel = a.model.compareTo(b.model);
        if (byModel != 0) return byModel;
        return a.leadDay.compareTo(b.leadDay);
      });
    return Column(
      children: [
        Row(
          children: [
            Expanded(child: Text(l10n.skillCellStation, style: header)),
            SizedBox(width: 64, child: Text('Model', style: header)),
            SizedBox(width: 48, child: Text(l10n.legendLeadAxis, style: header)),
            SizedBox(
              width: 68,
              child: Text('vs Clim', style: header, textAlign: TextAlign.right),
            ),
            SizedBox(
              width: 68,
              child: Text('vs Pers', style: header, textAlign: TextAlign.right),
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
                  child: Text(cell.location, style: theme.textTheme.bodySmall),
                ),
                SizedBox(
                  width: 64,
                  child: Text(
                    cell.model == 'gfs_seamless'
                        ? 'GFS'
                        : (cell.model == 'ecmwf_ifs025' ? 'ECMWF' : cell.model),
                    style: theme.textTheme.bodySmall,
                  ),
                ),
                SizedBox(
                  width: 48,
                  child: Text(
                    l10n.leadDay(cell.leadDay),
                    style: theme.textTheme.bodySmall,
                  ),
                ),
                SizedBox(
                  width: 68,
                  child: Text(
                    cell.insufficient
                        ? '—'
                        : _crpss(cell.crpssVsClimatology, locale: locale),
                    textAlign: TextAlign.right,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: !cell.insufficient &&
                              (cell.crpssVsClimatology ?? 0) < 0
                          ? theme.colorScheme.error
                          : null,
                    ),
                  ),
                ),
                SizedBox(
                  width: 68,
                  child: Text(
                    cell.insufficient
                        ? '—'
                        : _crpss(cell.crpssVsPersistence, locale: locale),
                    textAlign: TextAlign.right,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: !cell.insufficient &&
                              (cell.crpssVsPersistence ?? 0) < 0
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
