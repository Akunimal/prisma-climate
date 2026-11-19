import 'package:flutter_test/flutter_test.dart';
import 'package:prisma_app/src/map_tiles.dart';

void main() {
  group('resolveGibsDate', () {
    test('early UTC window (00:00 - 05:59 UTC) resolves to D-2', () {
      final earlyMorning = DateTime.utc(2026, 11, 19, 2, 0);
      expect(resolveGibsDate(earlyMorning), '2026-11-17');

      final boundaryEarly = DateTime.utc(2026, 11, 19, 5, 59, 59);
      expect(resolveGibsDate(boundaryEarly), '2026-11-17');
    });

    test('consolidated UTC window (06:00 - 23:59 UTC) resolves to D-1', () {
      final boundaryConsolidated = DateTime.utc(2026, 11, 19, 6, 0);
      expect(resolveGibsDate(boundaryConsolidated), '2026-11-18');

      final noon = DateTime.utc(2026, 11, 19, 12, 0);
      expect(resolveGibsDate(noon), '2026-11-18');

      final lateNight = DateTime.utc(2026, 11, 19, 23, 59, 59);
      expect(resolveGibsDate(lateNight), '2026-11-18');
    });

    test('handles year crossover correctly', () {
      final newYearMorning = DateTime.utc(2026, 1, 1, 3, 0);
      expect(resolveGibsDate(newYearMorning), '2025-12-30');
    });

    test('handles leap year correctly', () {
      final leapDayMorning = DateTime.utc(2024, 3, 1, 8, 0);
      expect(resolveGibsDate(leapDayMorning), '2024-02-29');

      final leapDayEarly = DateTime.utc(2024, 3, 1, 2, 0);
      expect(resolveGibsDate(leapDayEarly), '2024-02-28');
    });

    test('supports fallback extraDaysBack and treats negative days as 0', () {
      final noon = DateTime.utc(2026, 11, 19, 12, 0);
      expect(resolveGibsDate(noon, 1), '2026-11-17');
      expect(resolveGibsDate(noon, 2), '2026-11-16');
      expect(resolveGibsDate(noon, -3), '2026-11-18');
    });

    test('clamps dates older than min archive date', () {
      final ancient = DateTime.utc(2010, 1, 1);
      expect(resolveGibsDate(ancient), '2015-11-24');
    });

    test('converts local DateTime to UTC deterministically', () {
      // Create a local DateTime and ensure its UTC representation matches expected
      final localDate = DateTime(2026, 11, 19, 12, 0);
      final expectedUtc = localDate.toUtc();
      expect(resolveGibsDate(localDate), resolveGibsDate(expectedUtc));
    });
  });

  group('buildGibsTileUrlTemplate', () {
    test('constructs exact WMTS REST template with {z}/{y}/{x} order', () {
      final noon = DateTime.utc(2026, 11, 19, 12, 0);
      final url = buildGibsTileUrlTemplate(now: noon);

      expect(
        url,
        'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/'
        'VIIRS_SNPP_CorrectedReflectance_TrueColor/default/2026-11-18/'
        'GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg',
      );
      expect(url.endsWith('/{z}/{y}/{x}.jpg'), isTrue);
    });

    test('respects extraDaysBack in URL template', () {
      final noon = DateTime.utc(2026, 11, 19, 12, 0);
      final url = buildGibsTileUrlTemplate(now: noon, extraDaysBack: 1);

      expect(url, contains('/default/2026-11-17/'));
    });
  });
}
