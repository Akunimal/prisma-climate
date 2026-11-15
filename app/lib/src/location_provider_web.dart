import 'dart:async';
import 'dart:js_interop';

import 'package:web/web.dart' as web;

import 'location_provider.dart';
import 'nearest_station.dart';

LocationProvider createLocationProvider() => const WebLocationProvider();

class WebLocationProvider implements LocationProvider {
  const WebLocationProvider();

  @override
  Future<GeoPoint> currentPosition() {
    final completer = Completer<GeoPoint>();
    try {
      web.window.navigator.geolocation.getCurrentPosition(
        ((web.GeolocationPosition position) {
          if (completer.isCompleted) {
            return;
          }
          completer.complete(
            GeoPoint(
              lat: position.coords.latitude,
              lon: position.coords.longitude,
            ),
          );
        }).toJS,
        ((web.GeolocationPositionError error) {
          if (completer.isCompleted) {
            return;
          }
          completer.completeError(LocationException(_kind(error.code)));
        }).toJS,
      );
    } catch (_) {
      return Future<GeoPoint>.error(
        const LocationException(LocationErrorKind.unavailable),
      );
    }
    return completer.future.timeout(
      const Duration(seconds: 15),
      onTimeout: () => throw const LocationException(LocationErrorKind.timeout),
    );
  }

  LocationErrorKind _kind(int code) => switch (code) {
    1 => LocationErrorKind.denied,
    3 => LocationErrorKind.timeout,
    _ => LocationErrorKind.unavailable,
  };
}
