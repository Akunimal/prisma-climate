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
}
