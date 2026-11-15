// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Portuguese (`pt`).
class AppLocalizationsPt extends AppLocalizations {
  AppLocalizationsPt([String locale = 'pt']) : super(locale);

  @override
  String get appTitle => 'PRISMA · Previsão por estação';

  @override
  String get appTagline =>
      'Ensamble bruto do Open-Meteo (GFS e ECMWF IFS) para 19 estações na Argentina.';

  @override
  String get tabStations => 'Estações';

  @override
  String get tabForecast => 'Previsão';

  @override
  String get tabSkill => 'Skill';

  @override
  String get tabAbout => 'Sobre / Estado';

  @override
  String get searchHint => 'Buscar estações ou locais';

  @override
  String get searchNoResults => 'Nenhuma estação corresponde à busca.';

  @override
  String get stationsIntro => 'Escolha uma estação para ver a previsão.';

  @override
  String get clearSearch => 'Limpar';

  @override
  String get retry => 'Tentar novamente';

  @override
  String get loading => 'Carregando dados…';

  @override
  String get labelIssue => 'Emissão';

  @override
  String get labelExported => 'Exportado';

  @override
  String get labelSmn => 'Observações SMN';

  @override
  String get labelClimateZone => 'Zona climática';

  @override
  String get labelCoordinates => 'Coordenadas';

  @override
  String get argentinaTimeNote => 'Hora da Argentina (UTC−3)';

  @override
  String get variableT2mMax => 'Máxima diária (t2m_max)';

  @override
  String get variableT2mMin => 'Mínima diária (t2m_min)';

  @override
  String get variablePrecip => 'Precipitação (fração de membros)';

  @override
  String get legendBand1090 => 'Faixa 10–90 %';

  @override
  String get legendBand2575 => 'Faixa 25–75 %';

  @override
  String get legendMedian => 'Mediana';

  @override
  String get legendModelsNeverPooled =>
      'Cada modelo mantém seus próprios membros e seus próprios percentis; eles nunca são combinados.';

  @override
  String get legendLeadAxis => 'Dia de antecedência';

  @override
  String get noData => 'sem dados';

  @override
  String get missingMembersTitle => 'Sem dados';

  @override
  String missingMembers(int members, int nominal) {
    return 'sem dados ($members/$nominal membros)';
  }

  @override
  String get observedTitle => 'Observado pelo SMN — últimos 30 dias';

  @override
  String get observedNote =>
      'Valores arquivados como servidos pelo SMN; lacunas permanecem null e nunca são preenchidas.';

  @override
  String get observedDate => 'Data';

  @override
  String get observedMax => 'Máx';

  @override
  String get observedMin => 'Mín';

  @override
  String get precipTitle => 'Precipitação';

  @override
  String get precipGe1 => '≥ 1 mm';

  @override
  String get precipGe10 => '≥ 10 mm';

  @override
  String get precipNote =>
      'Fração de membros utilizáveis com precipitação diária acumulada igual ou acima do limiar.';

  @override
  String get day => 'Dia';

  @override
  String get date => 'Data';

  @override
  String get model => 'Modelo';

  @override
  String get rawBanner =>
      'Previsão de ensamble bruta: sem correção de viés e não calibrada. Nenhuma métrica de verificação é publicada antes do limiar de 15 datas de emissão.';

  @override
  String get attributionTitle => 'Dados e atribuição';

  @override
  String get attributionObserved =>
      'Séries observadas: Servicio Meteorológico Nacional, arquivadas como servidas; lacunas permanecem null e nunca são preenchidas.';

  @override
  String get attributionNote =>
      'As linhas de atribuição são reproduzidas literalmente como exigem suas licenças; apenas a explicação ao redor é traduzida.';

  @override
  String get aboutTitle => 'Sobre / Estado';

  @override
  String get aboutWhatTitle => 'O que este app mostra';

  @override
  String get aboutWhat =>
      'O PRISMA publica, para 19 estações da Argentina, a previsão probabilística bruta de dois ensambles (ECMWF IFS e GFS) até 15 dias de antecedência, além das temperaturas máxima e mínima observadas pelo SMN nos últimos 30 dias. O app lê apenas arquivos estáticos publicados no GitHub Pages: não há servidor nem API.';

  @override
  String get aboutNoSkillTitle => 'Métricas de skill operacionais';

  @override
  String get aboutNoSkill =>
      'Resultados de verificação operacionais (CRPS, CRPSS, Brier, confiabilidade, cobertura, ranking) não são publicados antes do limiar de 15 datas de emissão. A tela Skill mostra apenas escores de calibração rotulados hindcast, de uma repetição histórica; nunca são misturados com o arquivo operacional.';

  @override
  String get skillTitle => 'Skill de calibração (hindcast)';

  @override
  String get skillHindcastBanner =>
      'Somente hindcast: esses escores vêm de uma repetição histórica contra observações arquivadas, não do arquivo de previsões ao vivo. Nunca são misturados com a verificação operacional.';

  @override
  String get skillUnavailable =>
      'Ainda não há uma execução de calibração hindcast disponível.';

  @override
  String get skillLabel => 'Rótulo';

  @override
  String get skillMeanEmos => 'CRPSS médio (EMOS vs bruto)';

  @override
  String get skillMeanQm => 'CRPSS médio (QM vs bruto)';

  @override
  String skillCellsCount(int sufficient, int total) {
    return '$sufficient de $total células com dados de treino suficientes';
  }

  @override
  String get skillDidNotBeat =>
      'CRPSS médio ≤ 0: nesta janela hindcast a calibração não superou o ensamble bruto.';

  @override
  String get skillProvider => 'Provedor';

  @override
  String get skillWindow => 'Janela';

  @override
  String get skillRetrieved => 'Obtido';

  @override
  String get skillLeads => 'Antecedências';

  @override
  String get skillMode => 'Modo';

  @override
  String get skillGateTitle => 'Limiar operacional';

  @override
  String skillGateArchived(int archived, int required) {
    return 'Datas de emissão arquivadas: $archived de $required';
  }

  @override
  String get skillGateOpen =>
      'Limiar aberto — o ranking operacional pode ser publicado.';

  @override
  String get skillGateClosed =>
      'Limiar fechado — o ranking operacional não é publicado.';

  @override
  String get skillCellsTitle => 'Células por estação e antecedência';

  @override
  String get skillCellStation => 'Estação';

  @override
  String get comparatorTitle => 'Comparação de fontes';

  @override
  String get comparatorNote =>
      'Percentis da máxima diária lado a lado por modelo (°C): p10–p90 · mediana. Nunca combinados.';

  @override
  String get aboutStatusTitle => 'Estado dos dados';

  @override
  String get aboutSourcesTitle => 'Fontes e licenças';

  @override
  String get aboutDataset => 'Conjunto de dados';

  @override
  String get aboutSmnSnapshot => 'Instantâneo SMN (regtemp)';

  @override
  String get aboutRegion => 'Região';

  @override
  String get aboutSchema => 'Esquema';

  @override
  String get statusForecasts =>
      'Membros de ensamble brutos: sem correção de viés, não calibrados e sem controle de qualidade além do flag de qualidade da fonte.';

  @override
  String get statusVerification =>
      'Nenhum resultado de verificação (CRPS, CRPSS, Brier, confiabilidade, cobertura, ranking) é publicado antes do limiar de 15 datas de emissão em docs/EVALUATION_PROTOCOL.md.';

  @override
  String get statusObservations =>
      'O instantâneo SMN regtemp é arquivado como servido; lacunas permanecem null e nunca são preenchidas. Aplica-se a regra de precedência de produtos de 2026-11-14 (regtemp primário).';

  @override
  String get aboutMachineTranslations =>
      'As traduções além do inglês são geradas por máquina; correções e melhorias são bem-vindas.';

  @override
  String get languageLabel => 'Idioma';

  @override
  String leadDay(int lead) {
    return '+$lead d';
  }

  @override
  String errorTitle(String document) {
    return 'Não foi possível ler $document';
  }

  @override
  String schemaUnsupported(String version) {
    return 'A versão do esquema \"$version\" não é suportada por este app (esperado 1.0). Atualize o app ou o export.';
  }

  @override
  String parseError(String document, String detail) {
    return 'O documento $document não está no formato esperado: $detail';
  }

  @override
  String networkError(String document, String detail) {
    return 'Não foi possível baixar $document: $detail';
  }

  @override
  String httpError(int status, String document) {
    return 'A fonte de dados retornou HTTP $status para $document.';
  }

  @override
  String invalidJson(String document, String detail) {
    return 'JSON inválido em $document: $detail';
  }

  @override
  String get modelsNonText =>
      'O campo \"models\" contém um valor que não é texto.';

  @override
  String fieldNotObject(String field) {
    return 'O campo \"$field\" não é um objeto JSON.';
  }

  @override
  String fieldNotArray(String field) {
    return 'O campo \"$field\" não é um array JSON.';
  }

  @override
  String missingTextField(String field) {
    return 'Falta o campo de texto \"$field\" ou não é uma string.';
  }

  @override
  String missingIntegerField(String field) {
    return 'Falta o inteiro \"$field\" ou não é um número.';
  }

  @override
  String notNumericField(String field) {
    return 'O campo \"$field\" não é numérico.';
  }

  @override
  String missingSchemaVersion(String document) {
    return 'Falta o campo schema_version em $document.';
  }

  @override
  String stationCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count estações',
      one: '$count estação',
    );
    return '$_temp0';
  }

  @override
  String get stationsViewList => 'Lista';

  @override
  String get stationsViewMap => 'Mapa';

  @override
  String get stationsViewForecast => 'Ver previsao';

  @override
  String get mapLegend => 'Legenda';

  @override
  String get mapReportProblem => 'Reportar um problema do mapa';

  @override
  String get mapTilesFailed =>
      'Nao foi possivel carregar os mosaicos do mapa. As estacoes sao mostradas sobre um fundo neutro.';

  @override
  String get aboutMapTilesTitle => 'Mosaicos do mapa';

  @override
  String get aboutMapTilesNote =>
      'O mapa carrega seus mosaicos diretamente dos servidores do OpenStreetMap.';

  @override
  String get searchStationsGroup => 'Estações';

  @override
  String get searchPlacesGroup => 'Locais';

  @override
  String get placesUnavailable =>
      'A busca de locais não está disponível no momento.';

  @override
  String nearestStation(String station) {
    return 'Estação mais próxima: $station';
  }

  @override
  String distanceKm(String km) {
    return 'Distância: $km km';
  }

  @override
  String get nearestStationWarning =>
      'Nenhuma estação a menos de 100 km — a previsão é da estação mais próxima, que pode não representar sua localização.';

  @override
  String get useMyLocation => 'Usar minha localização';

  @override
  String get locationDenied =>
      'Permissão de localização negada. Busque um local.';

  @override
  String get locationUnavailable =>
      'A localização não está disponível neste dispositivo.';

  @override
  String get locationTimeout =>
      'Não foi possível obter sua localização. Tente novamente ou busque um local.';

  @override
  String get yourLocation => 'Sua localização';

  @override
  String get aboutPlacesTitle => 'Dados de locais';

  @override
  String get aboutPlacesNote =>
      'Os nomes de locais vêm do GeoNames e são usados apenas para busca neste dispositivo.';

  @override
  String get aboutPrivacyTitle => 'Privacidade';

  @override
  String get aboutPrivacyNote =>
      'A busca de locais e a localização ficam neste dispositivo; apenas os mosaicos do mapa são solicitados ao provedor do mapa.';
}
