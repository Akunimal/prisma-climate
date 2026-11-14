const String kPrismaTileUrlTemplate = String.fromEnvironment(
  'PRISMA_TILE_URL',
  defaultValue: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
);

const String kPrismaTileAttribution = '\u00a9 OpenStreetMap contributors';

const String kPrismaTileUserAgent = 'prisma_climate';
