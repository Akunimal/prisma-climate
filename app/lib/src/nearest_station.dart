import 'dart:math' as math;

import 'data/models.dart';

/// Above this distance the app warns that the nearest station may not
/// represent the place or the user.
const double kNearestStationWarningKm = 100.0;

const double _earthRadiusKm = 6371.0088;

class GeoPoint {
  const GeoPoint({required this.lat, required this.lon});

  final double lat;
  final double lon;
}

class NearestStation {
  const NearestStation({required this.station, required this.distanceKm});

  final StationSummary station;
  final double distanceKm;
}

double haversineKm(GeoPoint a, GeoPoint b) {
  final dLat = _radians(b.lat - a.lat);
  final dLon = _radians(b.lon - a.lon);
  final lat1 = _radians(a.lat);
  final lat2 = _radians(b.lat);
  final h = math.sin(dLat / 2) * math.sin(dLat / 2) +
      math.cos(lat1) *
          math.cos(lat2) *
          math.sin(dLon / 2) *
          math.sin(dLon / 2);
  return 2 * _earthRadiusKm * math.asin(math.min(1, math.sqrt(h)));
}

double _radians(double degrees) => degrees * math.pi / 180.0;

/// Nearest station by great-circle distance; ties go to station name, then id.
NearestStation? nearestStation(GeoPoint point, List<StationSummary> stations) {
  NearestStation? best;
  for (final station in stations) {
    final distance = haversineKm(
      point,
      GeoPoint(lat: station.lat, lon: station.lon),
    );
    if (best == null) {
      best = NearestStation(station: station, distanceKm: distance);
      continue;
    }
    final delta = distance - best.distanceKm;
    if (delta < -1e-9) {
      best = NearestStation(station: station, distanceKm: distance);
      continue;
    }
    if (delta.abs() <= 1e-9) {
      final byName =
          station.name.toLowerCase().compareTo(best.station.name.toLowerCase());
      if (byName < 0 || (byName == 0 && station.id.compareTo(best.station.id) < 0)) {
        best = NearestStation(station: station, distanceKm: distance);
      }
    }
  }
  return best;
}
