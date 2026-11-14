import 'package:material_ui/material_ui.dart';

import 'src/app.dart';
import 'src/data/repository.dart';

// Relative to the page by default; override at build time with
// `--dart-define=PRISMA_DATA_BASE_URL=https://host/path/data/`.
const String dataBaseUrl = String.fromEnvironment(
  'PRISMA_DATA_BASE_URL',
  defaultValue: 'data/',
);

void main() {
  runApp(PrismaApp(repository: PrismaRepository(baseUrl: dataBaseUrl)));
}
