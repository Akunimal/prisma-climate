import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/models.dart';
import '../format.dart';
import '../l10n.dart';
import '../map_tiles.dart';
import '../widgets/common.dart';

Future<void> _open(String url) async {
  final uri = Uri.tryParse(url);
  if (uri == null) {
    return;
  }
  await launchUrl(uri, mode: LaunchMode.externalApplication);
}

class AboutScreen extends StatelessWidget {
  const AboutScreen({super.key, required this.about, required this.latest});

  final AboutDocument about;
  final LatestDocument latest;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = context.l10n;
    final statusTexts = <String, String>{
      'forecasts': l10n.statusForecasts,
      'verification': l10n.statusVerification,
      'observations': l10n.statusObservations,
    };
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      children: [
        SectionCard(
          title: l10n.aboutWhatTitle,
          child: Text(l10n.aboutWhat),
        ),
        SectionCard(
          title: l10n.aboutNoSkillTitle,
          child: Text(l10n.aboutNoSkill),
        ),
        SectionCard(
          title: l10n.aboutStatusTitle,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (final key in aboutStatusKeys)
                if (about.status.containsKey(key))
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(statusTexts[key]!),
                  ),
              if (!aboutStatusKeys.any(about.status.containsKey))
                EmptyNote(message: l10n.noData),
            ],
          ),
        ),
        SectionCard(
          title: l10n.aboutSourcesTitle,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (final source in about.sources)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(source.name, style: theme.textTheme.titleSmall),
                      Text(
                        source.role,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Wrap(
                        spacing: 10,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          TextButton(
                            onPressed: () => _open(source.attributionUrl),
                            child: Text(source.attribution),
                          ),
                          InkWell(
                            onTap: () => _open(source.licenceUrl),
                            child: Text(
                              source.licence,
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: theme.colorScheme.primary,
                                decoration: TextDecoration.underline,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
        SectionCard(
          title: l10n.aboutDataset,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              TextButton(
                onPressed: () => _open(about.datasetUrl),
                child: Text(about.datasetUrl),
              ),
              _MetadataRow(label: l10n.aboutRegion, value: about.region.name),
              _MetadataRow(
                label: l10n.labelExported,
                value: argentinaDateTime(
                  about.generatedAt,
                  locale: context.localeTag,
                ),
              ),
              _MetadataRow(
                label: l10n.aboutSmnSnapshot,
                value: about.smnSnapshotDate ?? '—',
              ),
              _MetadataRow(label: l10n.aboutSchema, value: latest.schemaVersion),
            ],
          ),
        ),
        SectionCard(
          title: l10n.aboutMapTilesTitle,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(l10n.aboutMapTilesNote),
              const SizedBox(height: 4),
              TextButton(
                onPressed: () => _open('https://www.openstreetmap.org/copyright'),
                child: const Text(kPrismaTileAttribution),
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Text(
            l10n.aboutMachineTranslations,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ),
      ],
    );
  }
}

class _MetadataRow extends StatelessWidget {
  const _MetadataRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 150,
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
