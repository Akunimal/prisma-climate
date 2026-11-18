import 'package:flutter_test/flutter_test.dart';
import 'package:prisma_app/src/station_bounds.dart';
import 'package:prisma_app/src/data/models.dart';

StationSummary make(String id, double lat, double lon, String zone) =>
    StationSummary(id: id, name: id, lat: lat, lon: lon, climateZone: zone);

void main() {
  test('empty list returns null', () {
    expect(computeStationBounds(<StationSummary>[]), isNull);
  });

  test('single station returns non-null bounds', () {
    final b = computeStationBounds(<StationSummary>[make('a', 10, 20, 'Pampa')]);
    expect(b, isNotNull);
  });

  test('multiple stations bounds contain all points', () {
    final stations = <StationSummary>[
      make('a', -10, -20, 'Pampa'),
      make('b', 5, 15, 'NOA'),
    ];
    final b = computeStationBounds(stations)!;
    expect(b.southWest.latitude, lessThanOrEqualTo(-10));
    expect(b.northEast.latitude, greaterThanOrEqualTo(5));
  });

  test('global span exceeding 180 degrees frames full world', () {
    final stations = <StationSummary>[
      make('honolulu', 21.319, -157.922, 'Pacific'),
      make('fiji', -17.755, 177.443, 'Melanesia'),
    ];
    final b = computeStationBounds(stations)!;
    expect(b.southWest.longitude, equals(-180.0));
    expect(b.northEast.longitude, equals(180.0));
  });
}
