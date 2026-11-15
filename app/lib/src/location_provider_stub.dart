import 'location_provider.dart';
import 'nearest_station.dart';

LocationProvider createLocationProvider() => const _UnavailableLocationProvider();

class _UnavailableLocationProvider implements LocationProvider {
  const _UnavailableLocationProvider();

  @override
  Future<GeoPoint> currentPosition() async =>
      throw const LocationException(LocationErrorKind.unavailable);
}
