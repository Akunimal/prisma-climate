import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/models.dart';
import '../format.dart';
import '../strings.dart';
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
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      children: [
        SectionCard(
          title: S.aboutWhatTitle,
          child: Text(S.aboutWhat),
        ),
        SectionCard(
          title: S.aboutNoSkillTitle,
          child: Text(S.aboutNoSkill),
        ),
        SectionCard(
          title: S.aboutStatusTitle,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (final key in S.statusTexts.keys)
                if (about.status.containsKey(key))
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(S.statusTexts[key]!),
                  ),
              if (!about.status.keys.any(S.statusTexts.containsKey))
                const EmptyNote(message: S.noData),
            ],
          ),
        ),
        SectionCard(
          title: S.aboutSourcesTitle,
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
          title: S.aboutDataset,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              TextButton(
                onPressed: () => _open(about.datasetUrl),
                child: Text(about.datasetUrl),
              ),
              _MetadataRow(label: S.aboutRegion, value: about.region.name),
              _MetadataRow(
                label: S.labelExported,
                value: argentinaDateTime(about.generatedAt),
              ),
              _MetadataRow(
                label: S.aboutSmnSnapshot,
                value: about.smnSnapshotDate ?? '—',
              ),
              _MetadataRow(label: S.aboutSchema, value: latest.schemaVersion),
            ],
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
