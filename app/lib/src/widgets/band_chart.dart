import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';

import '../data/models.dart';
import '../strings.dart';

class BandSeries {
  const BandSeries({required this.label, required this.color, required this.cases});

  final String label;
  final Color color;
  final List<ForecastCase> cases;
}

class ForecastBandChart extends StatelessWidget {
  const ForecastBandChart({
    super.key,
    required this.leads,
    required this.series,
    this.dateForLead = const {},
  });

  final List<int> leads;
  final List<BandSeries> series;
  final Map<int, String> dateForLead;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return CustomPaint(
      painter: _BandPainter(
        leads: leads,
        series: series,
        dateForLead: dateForLead,
        ink: theme.colorScheme.onSurface,
        muted: theme.colorScheme.onSurfaceVariant,
        grid: theme.colorScheme.outlineVariant,
      ),
      size: Size.infinite,
    );
  }
}

class _BandPainter extends CustomPainter {
  _BandPainter({
    required this.leads,
    required this.series,
    required this.dateForLead,
    required this.ink,
    required this.muted,
    required this.grid,
  });

  final List<int> leads;
  final List<BandSeries> series;
  final Map<int, String> dateForLead;
  final Color ink;
  final Color muted;
  final Color grid;

  @override
  void paint(Canvas canvas, Size size) {
    final plot = Rect.fromLTRB(42, 10, size.width - 10, size.height - 26);
    if (plot.width <= 0 || plot.height <= 0) {
      return;
    }

    final byLead = <int, Map<String, ForecastCase>>{};
    for (var i = 0; i < leads.length; i++) {
      byLead[leads[i]] = {
        for (final item in series)
          if (_caseAt(item, leads[i]) != null) item.label: _caseAt(item, leads[i])!,
      };
    }

    final values = <double>[];
    for (final item in series) {
      for (final value in item.cases) {
        if (!value.isMissing) {
          final low = value.min ?? value.p10;
          final high = value.max ?? value.p90;
          if (low != null) {
            values.add(low);
          }
          if (high != null) {
            values.add(high);
          }
        }
      }
    }

    if (values.isEmpty) {
      _drawText(canvas, S.noData, plot.center, muted, 13, align: TextAlign.center);
      return;
    }

    var low = values.reduce(math.min);
    var high = values.reduce(math.max);
    if (high - low < 2) {
      low -= 1;
      high += 1;
    }
    final pad = (high - low) * 0.08;
    low -= pad;
    high += pad;

    double y(double value) =>
        plot.bottom - ((value - low) / (high - low)) * plot.height;

    final xStep = leads.length <= 1 ? 0.0 : plot.width / (leads.length - 1);
    double x(int index) => plot.left + index * xStep;

    final gridPaint = Paint()
      ..color = grid
      ..strokeWidth = 0.7;
    for (var tick = 0; tick <= 4; tick++) {
      final value = low + (high - low) * tick / 4;
      final yy = y(value);
      canvas.drawLine(Offset(plot.left, yy), Offset(plot.right, yy), gridPaint);
      _drawText(
        canvas,
        '${value.round()}°',
        Offset(plot.left - 6, yy),
        muted,
        9,
        align: TextAlign.right,
        vertical: true,
      );
    }

    for (var index = 0; index < leads.length; index += 2) {
      final label = dateForLead[leads[index]];
      if (label == null) {
        continue;
      }
      _drawText(
        canvas,
        label,
        Offset(x(index), plot.bottom + 6),
        muted,
        9,
        align: TextAlign.center,
      );
    }

    for (final item in series) {
      final points = <int, ForecastCase>{};
      for (final value in item.cases) {
        final index = leads.indexOf(value.leadDay);
        if (index >= 0) {
          points[index] = value;
        }
      }

      final segments = <List<int>>[];
      var current = <int>[];
      for (var index = 0; index < leads.length; index++) {
        final value = points[index];
        if (value != null && !value.isMissing && value.p10 != null && value.p90 != null) {
          current.add(index);
        } else if (current.isNotEmpty) {
          segments.add(current);
          current = <int>[];
        }
      }
      if (current.isNotEmpty) {
        segments.add(current);
      }

      for (final segment in segments) {
        if (segment.length < 2) {
          continue;
        }
        _fillBand(
          canvas,
          segment,
          x,
          y,
          (value) => value.p90!,
          (value) => value.p10!,
          item.color.withValues(alpha: 0.13),
          points,
        );
        final quartile = segment.every(
          (index) => points[index]!.p25 != null && points[index]!.p75 != null,
        );
        if (quartile) {
          _fillBand(
            canvas,
            segment,
            x,
            y,
            (value) => value.p75!,
            (value) => value.p25!,
            item.color.withValues(alpha: 0.22),
            points,
          );
        }

        final line = Path();
        var started = false;
        for (final index in segment) {
          final value = points[index]!.p50;
          if (value == null) {
            continue;
          }
          final point = Offset(x(index), y(value));
          if (!started) {
            line.moveTo(point.dx, point.dy);
            started = true;
          } else {
            line.lineTo(point.dx, point.dy);
          }
        }
        canvas.drawPath(
          line,
          Paint()
            ..color = item.color
            ..style = PaintingStyle.stroke
            ..strokeWidth = 2
            ..strokeCap = StrokeCap.round,
        );
        for (final index in segment) {
          final value = points[index]!.p50;
          if (value != null) {
            canvas.drawCircle(
              Offset(x(index), y(value)),
              2.4,
              Paint()..color = item.color,
            );
          }
        }
      }

      final missingPaint = Paint()
        ..color = muted.withValues(alpha: 0.7)
        ..strokeWidth = 1.1;
      for (var index = 0; index < leads.length; index++) {
        final value = points[index];
        if (value == null || !value.isMissing) {
          continue;
        }
        final center = Offset(x(index), plot.bottom - 7);
        canvas.drawLine(center.translate(-3, -3), center.translate(3, 3), missingPaint);
        canvas.drawLine(center.translate(-3, 3), center.translate(3, -3), missingPaint);
      }
    }
  }

  ForecastCase? _caseAt(BandSeries item, int leadDay) {
    for (final value in item.cases) {
      if (value.leadDay == leadDay) {
        return value;
      }
    }
    return null;
  }

  void _fillBand(
    Canvas canvas,
    List<int> segment,
    double Function(int) x,
    double Function(double) y,
    double Function(ForecastCase) upper,
    double Function(ForecastCase) lower,
    Color color,
    Map<int, ForecastCase> points,
  ) {
    final path = Path();
    for (var i = 0; i < segment.length; i++) {
      final index = segment[i];
      final offset = Offset(x(index), y(upper(points[index]!)));
      if (i == 0) {
        path.moveTo(offset.dx, offset.dy);
      } else {
        path.lineTo(offset.dx, offset.dy);
      }
    }
    for (var i = segment.length - 1; i >= 0; i--) {
      final index = segment[i];
      path.lineTo(x(index), y(lower(points[index]!)));
    }
    path.close();
    canvas.drawPath(path, Paint()..color = color);
  }

  @override
  bool shouldRepaint(covariant _BandPainter old) =>
      old.leads != leads || old.series != series;

  void _drawText(
    Canvas canvas,
    String text,
    Offset at,
    Color color,
    double size, {
    TextAlign align = TextAlign.left,
    bool vertical = false,
  }) {
    final painter = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(fontSize: size, color: color, fontFeatures: const []),
      ),
      textDirection: TextDirection.ltr,
      textAlign: align,
    )..layout(maxWidth: 90);
    var offset = at;
    if (align == TextAlign.center) {
      offset = at.translate(-painter.width / 2, 0);
    } else if (align == TextAlign.right) {
      offset = at.translate(-painter.width, 0);
    }
    if (vertical) {
      offset = offset.translate(0, -painter.height / 2);
    }
    painter.paint(canvas, offset);
  }
}

class ObservedChart extends StatelessWidget {
  const ObservedChart({super.key, required this.days});

  final List<ObservedDay> days;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return CustomPaint(
      painter: _ObservedPainter(
        days: days,
        maxColor: theme.colorScheme.error,
        minColor: theme.colorScheme.primary,
        muted: theme.colorScheme.onSurfaceVariant,
        grid: theme.colorScheme.outlineVariant,
      ),
      size: Size.infinite,
    );
  }
}

class _ObservedPainter extends CustomPainter {
  _ObservedPainter({
    required this.days,
    required this.maxColor,
    required this.minColor,
    required this.muted,
    required this.grid,
  });

  final List<ObservedDay> days;
  final Color maxColor;
  final Color minColor;
  final Color muted;
  final Color grid;

  @override
  void paint(Canvas canvas, Size size) {
    final plot = Rect.fromLTRB(42, 10, size.width - 10, size.height - 26);
    if (plot.width <= 0 || plot.height <= 0 || days.isEmpty) {
      return;
    }
    final values = <double>[];
    for (final day in days) {
      if (day.t2mMax != null) {
        values.add(day.t2mMax!);
      }
      if (day.t2mMin != null) {
        values.add(day.t2mMin!);
      }
    }
    if (values.isEmpty) {
      return;
    }
    var low = values.reduce(math.min) - 2;
    var high = values.reduce(math.max) + 2;
    double y(double value) =>
        plot.bottom - ((value - low) / (high - low)) * plot.height;
    final step = days.length <= 1 ? 0.0 : plot.width / (days.length - 1);
    double x(int index) => plot.left + index * step;

    final gridPaint = Paint()
      ..color = grid
      ..strokeWidth = 0.7;
    for (var tick = 0; tick <= 4; tick++) {
      final value = low + (high - low) * tick / 4;
      final yy = y(value);
      canvas.drawLine(Offset(plot.left, yy), Offset(plot.right, yy), gridPaint);
      _label(canvas, '${value.round()}°', Offset(plot.left - 6, yy), align: TextAlign.right);
    }

    for (var index = 0; index < days.length; index += 5) {
      final parts = days[index].date.split('-');
      final label = parts.length == 3 ? '${parts[2]}/${parts[1]}' : days[index].date;
      _label(canvas, label, Offset(x(index), plot.bottom + 6), align: TextAlign.center);
    }

    _line(canvas, (day) => day.t2mMax, x, y, maxColor);
    _line(canvas, (day) => day.t2mMin, x, y, minColor);
  }

  void _line(
    Canvas canvas,
    double? Function(ObservedDay) value,
    double Function(int) x,
    double Function(double) y,
    Color color,
  ) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.8;
    final path = Path();
    var started = false;
    for (var index = 0; index < days.length; index++) {
      final point = value(days[index]);
      if (point == null) {
        started = false;
        continue;
      }
      final offset = Offset(x(index), y(point));
      if (!started) {
        path.moveTo(offset.dx, offset.dy);
        started = true;
      } else {
        path.lineTo(offset.dx, offset.dy);
      }
    }
    canvas.drawPath(path, paint);
    for (var index = 0; index < days.length; index++) {
      final point = value(days[index]);
      if (point != null) {
        canvas.drawCircle(Offset(x(index), y(point)), 1.8, Paint()..color = color);
      }
    }
  }

  void _label(Canvas canvas, String text, Offset at, {TextAlign align = TextAlign.left}) {
    final painter = TextPainter(
      text: TextSpan(text: text, style: TextStyle(fontSize: 9, color: muted)),
      textDirection: TextDirection.ltr,
    )..layout(maxWidth: 90);
    var offset = at;
    if (align == TextAlign.center) {
      offset = at.translate(-painter.width / 2, 0);
    } else if (align == TextAlign.right) {
      offset = at.translate(-painter.width, -painter.height / 2);
    }
    painter.paint(canvas, offset);
  }

  @override
  bool shouldRepaint(covariant _ObservedPainter old) => old.days != days;
}
