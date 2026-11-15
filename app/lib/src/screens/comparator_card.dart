import 'package:material_ui/material_ui.dart';

import '../data/models.dart';
import '../format.dart';
import '../l10n.dart';
import '../model_labels.dart';
import '../widgets/common.dart';

/// Side-by-side model comparison for one variable: each model keeps its own
/// percentiles in its own column; values are never pooled or averaged.
class SourceComparatorCard extends StatelessWidget {
  const SourceComparatorCard({super.key, required this.document});

  final StationDocument document;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = context.l10n;
    final locale = context.localeTag;
    final models = document.models;
    final leads = document.leadDays;
    if (models.length < 2 || leads.isEmpty) {
      return SectionCard(
        title: l10n.comparatorTitle,
        child: EmptyNote(message: l10n.noData),
      );
    }

    final header = theme.textTheme.labelSmall?.copyWith(
      color: theme.colorScheme.onSurfaceVariant,
    );
    final dateForLead = <int, String>{};
    for (final model in models) {
      for (final item in document.casesFor('t2m_max', model)) {
        dateForLead[item.leadDay] = dayMonth(item.validLocalDate, locale: locale);
      }
    }

    return SectionCard(
      title: l10n.comparatorTitle,
      subtitle: l10n.comparatorNote,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 16,
            runSpacing: 6,
            children: [
              for (final model in models)
                LegendDot(color: modelColor(context, model), label: modelLabel(model)),
            ],
          ),
          const SizedBox(height: 10),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    SizedBox(width: 56, child: Text(l10n.legendLeadAxis, style: header)),
                    SizedBox(width: 64, child: Text(l10n.date, style: header)),
                    for (final model in models) ...[
                      SizedBox(
                        width: 148,
                        child: Text(
                          '${modelLabel(model)} · ${l10n.variableT2mMax}',
                          style: header,
                        ),
                      ),
                    ],
                  ],
                ),
                const Divider(height: 10),
                for (final lead in leads)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 3),
                    child: Row(
                      children: [
                        SizedBox(
                          width: 56,
                          child: Text(
                            l10n.leadDay(lead),
                            style: theme.textTheme.bodySmall,
                          ),
                        ),
                        SizedBox(
                          width: 64,
                          child: Text(
                            dateForLead[lead] ?? '—',
                            style: theme.textTheme.bodySmall,
                          ),
                        ),
                        for (final model in models)
                          SizedBox(
                            width: 148,
                            child: Text(
                              _cellText(
                                document.caseAt('t2m_max', model, lead),
                                l10n,
                                locale: locale,
                              ),
                              style: theme.textTheme.bodySmall?.copyWith(
                                fontFeatures: const [],
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 8),
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

String _cellText(ForecastCase? item, dynamic l10n, {String? locale}) {
  if (item == null || item.isMissing) {
    return item == null
        ? '—'
        : l10n.missingMembers(item.nMembers, item.nominalMembers);
  }
  String band(double? low, double? high) {
    if (low == null || high == null) {
      return '—';
    }
    return '${degreesCompact(low, locale: locale)}–${degreesCompact(high, locale: locale)}';
  }

  final median = degreesCompact(item.p50, locale: locale);
  return '${band(item.p10, item.p90)} · $median';
}
