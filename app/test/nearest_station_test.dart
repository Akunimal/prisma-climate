import 'package:flutter_test/flutter_test.dart';
import 'package:prisma_app/src/data/models.dart';
import 'package:prisma_app/src/nearest_station.dart';

StationSummary station({
  required String id,
  required String name,
  required double lat,
  required double lon,
}) {
  return StationSummary(
    id: id,
    name: name,
    lat: lat,
    lon: lon,
    climateZone: 'test',
  );
}

void main() {
  test('haversine: one degree of latitude is about 111.2 km', () {
    final distance = haversineKm(
      const GeoPoint(lat: 0, lon: 0),
      const GeoPoint(lat: 0, lon: 1),
    );
    expect(distance, closeTo(111.19, 0.05));
  });

  test('haversine: the same point is zero', () {
    expect(
      haversineKm(
        const GeoPoint(lat: -34.6, lon: -58.4),
        const GeoPoint(lat: -34.6, lon: -58.4),
      ),
      0,
    );
  });

  test('nearest station is the minimum distance', () {
    final nearest = nearestStation(
      const GeoPoint(lat: 0, lon: 0),
      [
        station(id: 'far', name: 'Far', lat: 10, lon: 10),
        station(id: 'near', name: 'Near', lat: 0, lon: 1),
      ],
    );
    expect(nearest, isNotNull);
    expect(nearest!.station.id, 'near');
    expect(nearest.distanceKm, closeTo(111.19, 0.05));
  });

  test('ties break by station name, then id', () {
    final nearest = nearestStation(
      const GeoPoint(lat: 0, lon: 0),
      [
        station(id: 'b', name: 'Bravo', lat: 0, lon: 1),
        station(id: 'a', name: 'Alfa', lat: 0, lon: -1),
      ],
    );
    expect(nearest!.station.name, 'Alfa');

    final sameName = nearestStation(
      const GeoPoint(lat: 0, lon: 0),
      [
        station(id: 'z', name: 'Same', lat: 0, lon: 1),
        station(id: 'a', name: 'Same', lat: 0, lon: -1),
      ],
    );
    expect(sameName!.station.id, 'a');
  });

  test('no stations gives no nearest station', () {
    expect(nearestStation(const GeoPoint(lat: 0, lon: 0), const []), isNull);
  });

  test('the warning threshold is 100 km', () {
    expect(kNearestStationWarningKm, 100.0);
  });
}
