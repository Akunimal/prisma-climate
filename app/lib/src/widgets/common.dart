import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/models.dart';
import '../l10n.dart';

/// Localised sentence for a data-layer failure. Kind-specific messages are
/// translated; the [DataException.message] fallback stays English.
String describeError(BuildContext context, Object error) {
  final l10n = context.l10n;
  if (error is DataException) {
    switch (error.kind) {
      case DataErrorKind.network:
        return l10n.networkError(error.document!, error.detail!);
      case DataErrorKind.http:
        return l10n.httpError(error.status!, error.document!);
      case DataErrorKind.parse:
        return l10n.parseError(error.document!, error.detail!);
      case DataErrorKind.invalidJson:
        return l10n.invalidJson(error.document!, error.detail!);
      case DataErrorKind.modelsNonText:
        return l10n.modelsNonText;
      case DataErrorKind.schema:
        return l10n.schemaUnsupported(error.detail!);
      case DataErrorKind.fieldNotObject:
        return l10n.fieldNotObject(error.field!);
      case DataErrorKind.fieldNotArray:
        return l10n.fieldNotArray(error.field!);
      case DataErrorKind.missingText:
        return l10n.missingTextField(error.field!);
      case DataErrorKind.missingInteger:
        return l10n.missingIntegerField(error.field!);
      case DataErrorKind.notNumeric:
        return l10n.notNumericField(error.field!);
      case DataErrorKind.missingSchema:
        return l10n.missingSchemaVersion(error.document!);
    }
  }
  return error.toString();
}

Color modelColor(BuildContext context, String model) {
  final scheme = Theme.of(context).colorScheme;
  final isDark = scheme.brightness == Brightness.dark;
  switch (model) {
    case 'ecmwf_ifs025':
      return scheme.primary;
    case 'gfs_seamless':
      return isDark ? const Color(0xFFFB923C) : const Color(0xFFB4531F);
    default:
      return scheme.tertiary;
  }
}

class SectionCard extends StatelessWidget {
  const SectionCard({
    super.key,
    required this.title,
    required this.child,
    this.subtitle,
    this.trailing,
  });

  final String title;
  final String? subtitle;
  final Widget? trailing;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      margin: const EdgeInsets.only(bottom: 14),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title, style: theme.textTheme.titleMedium),
                      if (subtitle != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Text(
                            subtitle!,
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
                ?trailing,              ],
            ),
            const SizedBox(height: 12),
            child,
          ],
        ),
      ),
    );
  }
}

class LegendDot extends StatelessWidget {
  const LegendDot({super.key, required this.color, required this.label});

  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(3),
          ),
        ),
        const SizedBox(width: 6),
        Text(label, style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}

class ErrorView extends StatelessWidget {
  const ErrorView({
    super.key,
    required this.title,
    required this.message,
    required this.onRetry,
  });

  final String title;
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 520),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.cloud_off, size: 40, color: theme.colorScheme.error),
              const SizedBox(height: 12),
              Text(title, style: theme.textTheme.titleMedium, textAlign: TextAlign.center),
              const SizedBox(height: 8),
              Text(message, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: Text(context.l10n.retry),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class LoadingView extends StatelessWidget {
  const LoadingView({super.key});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator(),
          const SizedBox(height: 12),
          Text(context.l10n.loading),
        ],
      ),
    );
  }
}

Future<void> _open(String url) async {
  final uri = Uri.tryParse(url);
  if (uri == null) {
    return;
  }
  await launchUrl(uri, mode: LaunchMode.externalApplication);
}

class AttributionBar extends StatelessWidget {
  const AttributionBar({super.key, required this.about});

  final AboutDocument about;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = context.l10n;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(l10n.attributionTitle, style: theme.textTheme.titleSmall),
        const SizedBox(height: 6),
        Wrap(
          spacing: 12,
          runSpacing: 4,
          children: [
            for (final source in about.sources)
              Wrap(
                crossAxisAlignment: WrapCrossAlignment.center,
                spacing: 4,
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
        Text(
          l10n.attributionNote,
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        Text(
          l10n.attributionObserved,
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }
}

class EmptyNote extends StatelessWidget {
  const EmptyNote({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Text(
        message,
        style: theme.textTheme.bodyMedium?.copyWith(
          color: theme.colorScheme.onSurfaceVariant,
        ),
      ),
    );
  }
}
