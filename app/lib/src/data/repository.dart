import 'dart:convert';

import 'package:http/http.dart' as http;

import '../strings.dart';
import 'models.dart';

class PrismaRepository {
  PrismaRepository({
    http.Client? client,
    this.baseUrl = 'data/',
    this.timeout = const Duration(seconds: 30),
  }) : _client = client ?? http.Client();

  final http.Client _client;
  final String baseUrl;
  final Duration timeout;

  Uri resolve(String path) {
    final base = Uri.parse(baseUrl);
    if (base.hasScheme) {
      return base.resolve(path);
    }
    return Uri.base.resolve('$baseUrl$path');
  }

  Future<LatestDocument> loadLatest({String document = 'latest.json'}) async =>
      LatestDocument.parse(await _getText(document), document: document);

  Future<AboutDocument> loadAbout({String document = 'about.json'}) async =>
      AboutDocument.parse(await _getText(document), document: document);

  Future<StationDocument> loadStation(String id) async {
    final document = 'stations/$id.json';
    return StationDocument.parse(await _getText(document), document: document);
  }

  Future<String> _getText(String document) async {
    final uri = resolve(document);
    final http.Response response;
    try {
      response = await _client.get(uri).timeout(timeout);
    } on Exception catch (error) {
      throw DataException(S.networkError(document, error.toString()));
    }
    if (response.statusCode != 200) {
      throw DataException(S.httpError(document, response.statusCode));
    }
    try {
      return utf8.decode(response.bodyBytes);
    } on FormatException catch (error) {
      throw DataException(S.parseError(document, error.message));
    }
  }

  void close() => _client.close();
}
