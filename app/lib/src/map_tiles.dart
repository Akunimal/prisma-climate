const String kPrismaTileUrlTemplate = String.fromEnvironment(
  'PRISMA_TILE_URL',
  defaultValue: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
);

const String kPrismaTileAttribution = '\u00a9 OpenStreetMap contributors';

const String kPrismaTileUserAgent = 'prisma_climate';

const String kPrismaGibsLayer = 'VIIRS_SNPP_CorrectedReflectance_TrueColor';
const String kPrismaGibsTileMatrixSet = 'GoogleMapsCompatible_Level9';
const String kPrismaGibsFormat = 'jpg';
const int kPrismaGibsMaxNativeZoom = 9;
const int kPrismaGibsSafetyOffsetHours = 30;
const int kPrismaGibsMaxFallbackDays = 1;
final DateTime kPrismaGibsMinArchiveDate = DateTime.utc(2015, 11, 24);
const String kPrismaGibsAttribution = 'NASA GIBS / EOSDIS';
const String kPrismaGibsAttributionUrl = 'https://gibs.earthdata.nasa.gov/';
const String kPrismaGibsUrlOverride = String.fromEnvironment(
  'PRISMA_GIBS_TILE_URL',
  defaultValue: '',
);

/// Resolves the target UTC date string (YYYY-MM-DD) for NASA GIBS TrueColor imagery.
///
/// VIIRS SNPP polar orbits require ~24 hours to sweep all longitudes plus ~3-5 hours
/// of processing latency. A safety offset of 30 hours ensures that between 00:00 and
/// 05:59 UTC date D-2 is fetched, and from 06:00 UTC onward date D-1 is fetched,
/// avoiding partial strips or 404 tile errors.
String resolveGibsDate([DateTime? now, int extraDaysBack = 0]) {
  final utcNow = (now ?? DateTime.now()).toUtc();
  final safeExtraDays = extraDaysBack < 0 ? 0 : extraDaysBack;
  var target = utcNow.subtract(
    Duration(hours: kPrismaGibsSafetyOffsetHours + (safeExtraDays * 24)),
  );
  if (target.isBefore(kPrismaGibsMinArchiveDate)) {
    target = kPrismaGibsMinArchiveDate;
  }
  final year = target.year.toString().padLeft(4, '0');
  final month = target.month.toString().padLeft(2, '0');
  final day = target.day.toString().padLeft(2, '0');
  return '$year-$month-$day';
}

/// Constructs the WMTS tile URL template for NASA GIBS EPSG:3857 VIIRS TrueColor.
/// Note WMTS coordinate order: {z}/{y}/{x}.
String buildGibsTileUrlTemplate({DateTime? now, int extraDaysBack = 0}) {
  final date = resolveGibsDate(now, extraDaysBack);
  if (kPrismaGibsUrlOverride.isNotEmpty) {
    return kPrismaGibsUrlOverride.replaceAll('{date}', date);
  }
  return 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/$kPrismaGibsLayer/default/$date/$kPrismaGibsTileMatrixSet/{z}/{y}/{x}.$kPrismaGibsFormat';
}
