import 'data/models.dart';

/// Case- and accent-insensitive normalisation shared by station and place search.
String normalizeSearchText(String value) {
  const replacements = {
    'á': 'a',
    'à': 'a',
    'ä': 'a',
    'â': 'a',
    'ã': 'a',
    'é': 'e',
    'è': 'e',
    'ë': 'e',
    'ê': 'e',
    'í': 'i',
    'ì': 'i',
    'ï': 'i',
    'î': 'i',
    'ó': 'o',
    'ò': 'o',
    'ö': 'o',
    'ô': 'o',
    'õ': 'o',
    'ú': 'u',
    'ù': 'u',
    'ü': 'u',
    'û': 'u',
    'ñ': 'n',
  };
  var out = value.toLowerCase();
  replacements.forEach((key, plain) => out = out.replaceAll(key, plain));
  return out;
}

/// Exact match first, then prefix, then substring; -1 when there is no match.
int searchRank(String candidate, String normalizedQuery) {
  final text = normalizeSearchText(candidate);
  if (text == normalizedQuery) {
    return 0;
  }
  if (text.startsWith(normalizedQuery)) {
    return 1;
  }
  if (text.contains(normalizedQuery)) {
    return 2;
  }
  return -1;
}

/// Places matching [query], ordered exact/prefix/substring, then population,
/// then place name and province. Ties stay deterministic.
List<PlaceRecord> rankPlaces(List<PlaceRecord> places, String query) {
  final normalized = normalizeSearchText(query.trim());
  if (normalized.isEmpty) {
    return const <PlaceRecord>[];
  }
  final scored = <({int rank, PlaceRecord place})>[];
  for (final place in places) {
    final rank = searchRank(place.name, normalized);
    if (rank >= 0) {
      scored.add((rank: rank, place: place));
    }
  }
  scored.sort((a, b) {
    final byRank = a.rank.compareTo(b.rank);
    if (byRank != 0) {
      return byRank;
    }
    final byPopulation = b.place.population.compareTo(a.place.population);
    if (byPopulation != 0) {
      return byPopulation;
    }
    final byName = a.place.name.toLowerCase().compareTo(b.place.name.toLowerCase());
    if (byName != 0) {
      return byName;
    }
    return a.place.admin1.toLowerCase().compareTo(b.place.admin1.toLowerCase());
  });
  return [for (final item in scored) item.place];
}
