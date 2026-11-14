const Duration argentinaOffset = Duration(hours: -3);

DateTime? parseUtc(String value) {
  final parsed = DateTime.tryParse(value);
  if (parsed == null) {
    return null;
  }
  return parsed.isUtc ? parsed : parsed.toUtc();
}

String two(int value) => value.toString().padLeft(2, '0');

String argentinaDateTime(String isoUtc) {
  final parsed = parseUtc(isoUtc);
  if (parsed == null) {
    return isoUtc;
  }
  final local = parsed.add(argentinaOffset);
  return '${two(local.day)}/${two(local.month)}/${local.year} ${two(local.hour)}:${two(local.minute)}';
}

String argentinaDate(String isoUtc) {
  final parsed = parseUtc(isoUtc);
  if (parsed == null) {
    return isoUtc;
  }
  final local = parsed.add(argentinaOffset);
  return '${two(local.day)}/${two(local.month)}/${local.year}';
}

String dayMonth(String isoDate) {
  final parts = isoDate.split('-');
  if (parts.length != 3) {
    return isoDate;
  }
  return '${parts[2]}/${parts[1]}';
}

String degrees(double? value) =>
    value == null ? '—' : '${value.toStringAsFixed(1)} °C';

String degreesCompact(double? value) =>
    value == null ? '—' : value.toStringAsFixed(0);

String percent(double? fraction) =>
    fraction == null ? '—' : '${(fraction * 100).round()} %';

String coordinates(double lat, double lon) =>
    '${lat.toStringAsFixed(2)}, ${lon.toStringAsFixed(2)}';
