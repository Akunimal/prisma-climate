import 'package:flutter/widgets.dart';
import 'package:material_ui/material_ui.dart'
    show GlobalMaterialLocalizations;

import '../l10n/generated/app_localizations.dart';

export '../l10n/generated/app_localizations.dart';

/// The ten locales the app ships, English first so unresolved languages fall
/// back to it.
const List<Locale> kSupportedLocales = <Locale>[
  Locale('en'),
  Locale('es'),
  Locale('pt'),
  Locale('fr'),
  Locale('de'),
  Locale('it'),
  Locale('ru'),
  Locale('zh'),
  Locale('ja'),
  Locale('hi'),
];

const List<LocalizationsDelegate<dynamic>> kLocalizationsDelegates =
    <LocalizationsDelegate<dynamic>>[
  AppLocalizations.delegate,
  ...GlobalMaterialLocalizations.delegates,
];

/// Language names in their own language (endonyms); never translated.
const Map<String, String> kLocaleEndonyms = <String, String>{
  'en': 'English',
  'es': 'Español',
  'pt': 'Português',
  'fr': 'Français',
  'de': 'Deutsch',
  'it': 'Italiano',
  'ru': 'Русский',
  'zh': '中文',
  'ja': '日本語',
  'hi': 'हिन्दी',
};

extension L10n on BuildContext {
  AppLocalizations get l10n => AppLocalizations.of(this);

  /// Resolved app locale as an intl tag (always one of [kSupportedLocales]).
  String get localeTag => Localizations.localeOf(this).toString();
}
