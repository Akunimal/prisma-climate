import 'package:flutter_test/flutter_test.dart';
import 'package:prisma_app/src/data/models.dart';
import 'package:prisma_app/src/search_text.dart';

PlaceRecord place({
  required String name,
  required String admin1,
  required int population,
  double lat = 0,
  double lon = 0,
}) {
  return PlaceRecord(
    name: name,
    admin1: admin1,
    lat: lat,
    lon: lon,
    population: population,
  );
}

void main() {
  test('normalisation folds case and accents', () {
    expect(normalizeSearchText('Córdoba'), 'cordoba');
    expect(normalizeSearchText('LA QUIACA'), 'la quiaca');
    expect(normalizeSearchText('San Martín'), 'san martin');
  });

  test('rank order is exact, then prefix, then substring', () {
    final ranked = rankPlaces(
      [
        place(name: 'Nueva Cordoba', admin1: 'Cordoba', population: 500),
        place(name: 'Cordoba Norte', admin1: 'Cordoba', population: 999),
        place(name: 'Cordoba', admin1: 'Cordoba', population: 1),
      ],
      'cordoba',
    );
    expect(
      ranked.map((item) => item.name).toList(),
      ['Cordoba', 'Cordoba Norte', 'Nueva Cordoba'],
    );
  });

  test('same rank orders by population, then name and province', () {
    final ranked = rankPlaces(
      [
        place(name: 'La Paz', admin1: 'Entre Rios', population: 1000),
        place(name: 'La Paz', admin1: 'Mendoza', population: 2000),
        place(name: 'La Plata', admin1: 'Buenos Aires', population: 500),
      ],
      'la',
    );
    expect(
      ranked.map((item) => '${item.name}/${item.admin1}').toList(),
      ['La Paz/Mendoza', 'La Paz/Entre Rios', 'La Plata/Buenos Aires'],
    );
  });

  test('duplicate place names stay separate and are disambiguated by province', () {
    final ranked = rankPlaces(
      [
        place(name: 'La Paz', admin1: 'Mendoza', population: 10),
        place(name: 'La Paz', admin1: 'Entre Rios', population: 10),
      ],
      'la paz',
    );
    expect(ranked, hasLength(2));
    expect(ranked.first.admin1, 'Entre Rios');
  });

  test('an empty query returns no places', () {
    expect(rankPlaces([place(name: 'Cordoba', admin1: 'Cordoba', population: 1)], '  '),
        isEmpty);
  });

  test('no match returns no places', () {
    expect(
      rankPlaces([place(name: 'Cordoba', admin1: 'Cordoba', population: 1)], 'zzz'),
      isEmpty,
    );
  });
}
