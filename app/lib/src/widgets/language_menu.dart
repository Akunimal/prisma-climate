import 'package:material_ui/material_ui.dart';

import '../l10n.dart';

/// Globe icon in the app bar; opens the list of the ten shipped languages.
class LanguageMenu extends StatelessWidget {
  const LanguageMenu({super.key, required this.onSelected});

  final ValueChanged<Locale> onSelected;

  @override
  Widget build(BuildContext context) {
    final active = Localizations.localeOf(context).languageCode;
    return PopupMenuButton<Locale>(
      tooltip: context.l10n.languageLabel,
      icon: const Icon(Icons.language),
      onSelected: onSelected,
      itemBuilder: (context) => [
        for (final locale in kSupportedLocales)
          PopupMenuItem(
            value: locale,
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  width: 26,
                  child: locale.languageCode == active
                      ? const Icon(Icons.check, size: 18)
                      : null,
                ),
                Text(kLocaleEndonyms[locale.languageCode]!),
              ],
            ),
          ),
      ],
    );
  }
}
