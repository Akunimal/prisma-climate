import 'package:intl/intl.dart';

const Duration argentinaOffset = Duration(hours: -3);

DateTime? parseUtc(String value) {
  final parsed = DateTime.tryParse(value);
  if (parsed == null) {
    return null;
  }
  return parsed.isUtc ? parsed : parsed.toUtc();
}

String two(int value) => value.toString().padLeft(2, '0');

/// `isoUtc` rendered in Argentina time (always UTC−3), formatted with
/// [locale] (an intl tag such as `de`); the timezone itself never changes.
String argentinaDateTime(String isoUtc, {String? locale}) {
  final parsed = parseUtc(isoUtc);
  if (parsed == null) {
    return isoUtc;
  }
  final local = parsed.add(argentinaOffset);
  return DateFormat('dd/MM/yyyy HH:mm', locale).format(local);
}

String argentinaDate(String isoUtc, {String? locale}) {
  final parsed = parseUtc(isoUtc);
  if (parsed == null) {
    return isoUtc;
  }
  final local = parsed.add(argentinaOffset);
  return DateFormat('dd/MM/yyyy', locale).format(local);
}

/// `yyyy-MM-dd` → `dd/MM`, ordered as day/month in every locale.
String dayMonth(String isoDate, {String? locale}) {
  final day = _isoDay(isoDate);
  return day == null ? isoDate : DateFormat('dd/MM', locale).format(day);
}

/// `yyyy-MM-dd` → `dd/MM/yyyy` in [locale].
String dayMonthYear(String isoDate, {String? locale}) {
  final day = _isoDay(isoDate);
  return day == null ? isoDate : DateFormat('dd/MM/yyyy', locale).format(day);
}

DateTime? _isoDay(String isoDate) {
  final parts = isoDate.split('-');
  if (parts.length != 3) {
    return null;
  }
  final year = int.tryParse(parts[0]);
  final month = int.tryParse(parts[1]);
  final day = int.tryParse(parts[2]);
  if (year == null || month == null || day == null) {
    return null;
  }
  return DateTime(year, month, day);
}

String degrees(double? value, {String? locale}) =>
    value == null ? '—' : '${NumberFormat('0.0', locale).format(value)} °C';

String degreesCompact(double? value, {String? locale}) =>
    value == null ? '—' : NumberFormat('0', locale).format(value);

String percent(double? fraction, {String? locale}) =>
    fraction == null ? '—' : NumberFormat('0 %', locale).format(fraction);

String coordinates(double lat, double lon, {String? locale}) {
  final format = NumberFormat('0.00', locale);
  return '${format.format(lat)}, ${format.format(lon)}';
}
