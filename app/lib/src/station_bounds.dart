import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import 'data/models.dart';

LatLngBounds? computeStationBounds(List<StationSummary> stations) {
  if (stations.isEmpty) return null;
  var minLat = stations.first.lat;
  var maxLat = stations.first.lat;
  var minLon = stations.first.lon;
  var maxLon = stations.first.lon;
  for (final s in stations.skip(1)) {
    if (s.lat < minLat) minLat = s.lat;
    if (s.lat > maxLat) maxLat = s.lat;
    if (s.lon < minLon) minLon = s.lon;
    if (s.lon > maxLon) maxLon = s.lon;
  }
  if (minLat == maxLat) {
    minLat -= 0.5;
    maxLat += 0.5;
  }
  if (minLon == maxLon) {
    minLon -= 0.5;
    maxLon += 0.5;
  }
  return LatLngBounds(LatLng(minLat, minLon), LatLng(maxLat, maxLon));
}
