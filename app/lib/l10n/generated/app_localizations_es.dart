// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Spanish Castilian (`es`).
class AppLocalizationsEs extends AppLocalizations {
  AppLocalizationsEs([String locale = 'es']) : super(locale);

  @override
  String get appTitle => 'PRISMA · Pronóstico por estación';

  @override
  String get appTagline =>
      'Ensamble crudo de Open-Meteo (GFS y ECMWF IFS) para 19 estaciones de Argentina.';

  @override
  String get tabStations => 'Estaciones';

  @override
  String get tabForecast => 'Pronóstico';

  @override
  String get tabAbout => 'Acerca de / Estado';

  @override
  String get searchHint => 'Buscar estaciones';

  @override
  String get searchNoResults => 'Ninguna estación coincide con la búsqueda.';

  @override
  String get stationsIntro => 'Elegí una estación para ver su pronóstico.';

  @override
  String get clearSearch => 'Limpiar';

  @override
  String get retry => 'Reintentar';

  @override
  String get loading => 'Cargando datos…';

  @override
  String get labelIssue => 'Emisión';

  @override
  String get labelExported => 'Exportado';

  @override
  String get labelSmn => 'Observaciones SMN';

  @override
  String get labelClimateZone => 'Zona climática';

  @override
  String get labelCoordinates => 'Coordenadas';

  @override
  String get argentinaTimeNote => 'Hora de Argentina (UTC−3)';

  @override
  String get variableT2mMax => 'Máxima diaria (t2m_max)';

  @override
  String get variableT2mMin => 'Mínima diaria (t2m_min)';

  @override
  String get variablePrecip => 'Precipitación (fracción de miembros)';

  @override
  String get legendBand1090 => 'Banda 10–90 %';

  @override
  String get legendBand2575 => 'Banda 25–75 %';

  @override
  String get legendMedian => 'Mediana';

  @override
  String get legendModelsNeverPooled =>
      'Cada modelo conserva sus propios miembros y sus propios percentiles; nunca se mezclan.';

  @override
  String get legendLeadAxis => 'Día de anticipación';

  @override
  String get noData => 'sin datos';

  @override
  String get missingMembersTitle => 'Sin datos';

  @override
  String missingMembers(int members, int nominal) {
    return 'sin datos ($members/$nominal miembros)';
  }

  @override
  String get observedTitle => 'SMN observado — últimos 30 días';

  @override
  String get observedNote =>
      'Valores archivados tal como los sirve el SMN; los huecos quedan null y nunca se rellenan.';

  @override
  String get observedDate => 'Fecha';

  @override
  String get observedMax => 'Máx';

  @override
  String get observedMin => 'Mín';

  @override
  String get precipTitle => 'Precipitación';

  @override
  String get precipGe1 => '≥ 1 mm';

  @override
  String get precipGe10 => '≥ 10 mm';

  @override
  String get precipNote =>
      'Fracción de miembros utilizables con precipitación diaria acumulada igual o superior al umbral.';

  @override
  String get day => 'Día';

  @override
  String get date => 'Fecha';

  @override
  String get model => 'Modelo';

  @override
  String get rawBanner =>
      'Pronóstico de ensamble crudo: sin corrección de sesgo y sin calibrar. No se publican métricas de verificación antes del umbral de 15 fechas de emisión.';

  @override
  String get attributionTitle => 'Datos y atribución';

  @override
  String get attributionObserved =>
      'Series observadas: Servicio Meteorológico Nacional, archivadas tal como se sirven; los huecos quedan null y nunca se rellenan.';

  @override
  String get attributionNote =>
      'Las líneas de atribución se reproducen textualmente como exigen sus licencias; solo se traduce la explicación circundante.';

  @override
  String get aboutTitle => 'Acerca de / Estado';

  @override
  String get aboutWhatTitle => 'Qué muestra esta app';

  @override
  String get aboutWhat =>
      'PRISMA publica, para 19 estaciones de Argentina, el pronóstico probabilístico crudo de dos ensambles (ECMWF IFS y GFS) hasta 15 días de anticipación, más las temperaturas máxima y mínima observadas por el SMN en los últimos 30 días. La app solo lee archivos estáticos publicados en GitHub Pages: no hay servidor ni API.';

  @override
  String get aboutNoSkillTitle => 'Sin métricas de skill';

  @override
  String get aboutNoSkill =>
      'La app no muestra CRPS, CRPSS, Brier, fiabilidad, cobertura ni clasificación. Esos números no se publican antes del umbral de 15 fechas de emisión.';

  @override
  String get aboutStatusTitle => 'Estado de los datos';

  @override
  String get aboutSourcesTitle => 'Fuentes y licencias';

  @override
  String get aboutDataset => 'Conjunto de datos';

  @override
  String get aboutSmnSnapshot => 'Instantánea SMN (regtemp)';

  @override
  String get aboutRegion => 'Región';

  @override
  String get aboutSchema => 'Esquema';

  @override
  String get statusForecasts =>
      'Miembros de ensamble crudos: sin corrección de sesgo, sin calibrar y sin control de calidad más allá del flag de calidad de la fuente.';

  @override
  String get statusVerification =>
      'No se publican resultados de verificación (CRPS, CRPSS, Brier, fiabilidad, cobertura, clasificación) antes del umbral de 15 fechas de emisión en docs/EVALUATION_PROTOCOL.md.';

  @override
  String get statusObservations =>
      'La instantánea SMN regtemp se archiva tal como se sirve; los huecos quedan null y nunca se rellenan. Aplica la regla de precedencia de productos del 2026-11-14 (regtemp primario).';

  @override
  String get aboutMachineTranslations =>
      'Las traducciones distintas al inglés son generadas por máquina; se agradecen correcciones y mejoras.';

  @override
  String get languageLabel => 'Idioma';

  @override
  String leadDay(int lead) {
    return '+$lead d';
  }

  @override
  String errorTitle(String document) {
    return 'No se pudo leer $document';
  }

  @override
  String schemaUnsupported(String version) {
    return 'La versión de esquema \"$version\" no está soportada por esta app (se espera 1.0). Actualizá la app o el export.';
  }

  @override
  String parseError(String document, String detail) {
    return 'El documento $document no tiene el formato esperado: $detail';
  }

  @override
  String networkError(String document, String detail) {
    return 'No se pudo descargar $document: $detail';
  }

  @override
  String httpError(int status, String document) {
    return 'La fuente de datos devolvió HTTP $status para $document.';
  }

  @override
  String invalidJson(String document, String detail) {
    return 'JSON inválido en $document: $detail';
  }

  @override
  String get modelsNonText =>
      'El campo \"models\" contiene un valor que no es texto.';

  @override
  String fieldNotObject(String field) {
    return 'El campo \"$field\" no es un objeto JSON.';
  }

  @override
  String fieldNotArray(String field) {
    return 'El campo \"$field\" no es un arreglo JSON.';
  }

  @override
  String missingTextField(String field) {
    return 'Falta el campo de texto \"$field\" o no es una cadena.';
  }

  @override
  String missingIntegerField(String field) {
    return 'Falta el entero \"$field\" o no es un número.';
  }

  @override
  String notNumericField(String field) {
    return 'El campo \"$field\" no es numérico.';
  }

  @override
  String missingSchemaVersion(String document) {
    return 'Falta el campo schema_version en $document.';
  }

  @override
  String stationCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count estaciones',
      one: '$count estación',
    );
    return '$_temp0';
  }

  @override
  String get stationsViewList => 'Lista';

  @override
  String get stationsViewMap => 'Mapa';

  @override
  String get stationsViewForecast => 'Ver pronostico';

  @override
  String get mapLegend => 'Leyenda';

  @override
  String get mapReportProblem => 'Informar un problema del mapa';

  @override
  String get mapTilesFailed =>
      'No se pudieron cargar los mosaicos del mapa. Se muestran las estaciones sobre un fondo neutro.';

  @override
  String get aboutMapTilesTitle => 'Mosaicos del mapa';

  @override
  String get aboutMapTilesNote =>
      'El mapa carga sus mosaicos directamente desde los servidores de OpenStreetMap.';
}
