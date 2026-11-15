import 'location_provider_stub.dart'
    if (dart.library.js_interop) 'location_provider_web.dart' as impl;
import 'nearest_station.dart';

enum LocationErrorKind { denied, unavailable, timeout }

class LocationException implements Exception {
  const LocationException(this.kind);

  final LocationErrorKind kind;
}

abstract class LocationProvider {
  Future<GeoPoint> currentPosition();
}

/// Browser geolocation on the web; unavailable on platforms without it.
LocationProvider createLocationProvider() => impl.createLocationProvider();
