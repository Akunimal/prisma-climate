import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:prisma_app/src/l10n.dart';

const List<String> kLocales = <String>[
  'en',
  'es',
  'pt',
  'fr',
  'de',
  'it',
  'ru',
  'zh',
  'ja',
  'hi',
];

/// Keys whose value may legitimately be identical to English: unit strings
/// (never translated by the glossary) and words that are spelled the same in
/// that language.
const Set<String> kIdenticalAllowed = <String>{
  'precipGe1',
  'precipGe10',
  'leadDay',
  'tabStations',
  'tabSkill',
  'date',
  'observedDate',
  'observedMax',
  'observedMin',
  'legendMedian',
  'aboutRegion',
  'aboutSchema',
  'aboutDataset',
  'searchStationsGroup',
  'aboutPrivacyTitle',
};

Map<String, dynamic> readArb(String locale) =>
    jsonDecode(File('lib/l10n/app_$locale.arb').readAsStringSync())
        as Map<String, dynamic>;

Map<String, dynamic> placeholdersOf(Map<String, dynamic> arb, String key) {
  final meta = arb['@$key'];
  if (meta is! Map<String, dynamic>) {
    return <String, dynamic>{};
  }
  final placeholders = meta['placeholders'];
  if (placeholders is! Map<String, dynamic>) {
    return <String, dynamic>{};
  }
  return placeholders;
}

void main() {
  final Map<String, dynamic> template = readArb('en');
  final List<String> keys = template.keys
      .where((String key) => !key.startsWith('@'))
      .toList();

  test('the template declares all ten locales and the app agrees', () {
    expect(kLocales, contains(template['@@locale'] as String));
    expect(
      kSupportedLocales.map((locale) => locale.languageCode),
      kLocales,
    );
    expect(kLocaleEndonyms.keys.toList(), kLocales);
    expect(
      kLocaleEndonyms.values.every((String value) => value.trim().isNotEmpty),
      isTrue,
    );
  });

  for (final String locale in kLocales) {
    test('$locale carries every template key with a non-empty value', () {
      final arb = readArb(locale);
      expect(arb['@@locale'], locale);
      for (final String key in keys) {
        expect(arb.containsKey(key), isTrue, reason: '$locale misses $key');
        final value = arb[key];
        expect(
          value is String && value.trim().isNotEmpty,
          isTrue,
          reason: '$locale.$key must be a non-empty string',
        );
      }
      expect(arb.length, template.length, reason: '$locale has extra keys');
    });
  }

  for (final String locale in kLocales) {
    test('$locale keeps the template placeholders', () {
      final arb = readArb(locale);
      for (final String key in keys) {
        final expected = placeholdersOf(template, key);
        final actual = placeholdersOf(arb, key);
        expect(
          actual.keys.toSet(),
          expected.keys.toSet(),
          reason: '$locale.$key placeholder names differ',
        );
        for (final String name in expected.keys) {
          expect(
            (actual[name] as Map)['type'],
            (expected[name] as Map)['type'],
            reason: '$locale.$key placeholder $name type differs',
          );
        }
      }
    });
  }

  for (final String locale in kLocales.where((String l) => l != 'en')) {
    test('$locale translations differ from English outside the allowlist', () {
      final arb = readArb(locale);
      for (final String key in keys) {
        if (kIdenticalAllowed.contains(key)) {
          continue;
        }
        expect(
          arb[key],
          isNot(template[key]),
          reason: '$locale.$key was left in English',
        );
      }
    });
  }

  test('honesty phrases and never-translated units stay in every locale', () {
    for (final String locale in kLocales) {
      final arb = readArb(locale);
      final raw = arb['rawBanner'] as String;
      final gate = arb['statusVerification'] as String;
      final observations = arb['statusObservations'] as String;
      final observedNote = arb['observedNote'] as String;
      final attributionNote = arb['attributionNote'] as String;

      expect(raw.contains('15'), isTrue, reason: '$locale rawBanner gate');
      expect(gate.contains('15'), isTrue, reason: '$locale status gate');
      expect(
        gate.contains('docs/EVALUATION_PROTOCOL.md'),
        isTrue,
        reason: '$locale must name the protocol document',
      );
      expect(observedNote.contains('null'), isTrue, reason: '$locale gaps');
      expect(
        observations.contains('2026-11-14'),
        isTrue,
        reason: '$locale precedence rule',
      );
      expect(
        attributionNote.trim().isNotEmpty &&
            arb['attributionObserved'].toString().contains(
                  'Servicio Meteorológico Nacional',
                ),
        isTrue,
        reason: '$locale attribution',
      );
      if (locale != 'en') {
        expect(
          arb['aboutMachineTranslations'],
          isNot(template['aboutMachineTranslations']),
        );
      }

      expect(arb['precipGe1'], '≥ 1 mm');
      expect(arb['precipGe10'], '≥ 10 mm');
      expect(arb['leadDay'], '+{lead} d');
      expect(
        arb['argentinaTimeNote'].toString().contains('UTC−3'),
        isTrue,
        reason: '$locale Argentina time',
      );
    }
  });
}
