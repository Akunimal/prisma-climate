// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for French (`fr`).
class AppLocalizationsFr extends AppLocalizations {
  AppLocalizationsFr([String locale = 'fr']) : super(locale);

  @override
  String get appTitle => 'PRISMA · Prévision par station';

  @override
  String get appTagline =>
      'Ensamble brut d\'Open-Meteo (GFS et ECMWF IFS) pour 19 stations en Argentine.';

  @override
  String get tabStations => 'Stations';

  @override
  String get tabForecast => 'Prévisions';

  @override
  String get tabAbout => 'À propos / État';

  @override
  String get searchHint => 'Rechercher des stations';

  @override
  String get searchNoResults => 'Aucune station ne correspond à la recherche.';

  @override
  String get stationsIntro => 'Choisissez une station pour voir sa prévision.';

  @override
  String get clearSearch => 'Effacer';

  @override
  String get retry => 'Réessayer';

  @override
  String get loading => 'Chargement des données…';

  @override
  String get labelIssue => 'Émission';

  @override
  String get labelExported => 'Exporté';

  @override
  String get labelSmn => 'Observations SMN';

  @override
  String get labelClimateZone => 'Zone climatique';

  @override
  String get labelCoordinates => 'Coordonnées';

  @override
  String get argentinaTimeNote => 'Heure de l\'Argentine (UTC−3)';

  @override
  String get variableT2mMax => 'Maximum quotidien (t2m_max)';

  @override
  String get variableT2mMin => 'Minimum quotidien (t2m_min)';

  @override
  String get variablePrecip => 'Précipitation (fraction des membres)';

  @override
  String get legendBand1090 => 'Bande 10–90 %';

  @override
  String get legendBand2575 => 'Bande 25–75 %';

  @override
  String get legendMedian => 'Médiane';

  @override
  String get legendModelsNeverPooled =>
      'Chaque modèle conserve ses propres membres et ses propres centiles ; ils ne sont jamais mélangés.';

  @override
  String get legendLeadAxis => 'Jour de prévision';

  @override
  String get noData => 'aucune donnée';

  @override
  String get missingMembersTitle => 'Aucune donnée';

  @override
  String missingMembers(int members, int nominal) {
    return 'aucune donnée ($members/$nominal membres)';
  }

  @override
  String get observedTitle => 'Observé SMN — 30 derniers jours';

  @override
  String get observedNote =>
      'Valeurs archivées telles que servies par le SMN ; les trous restent null et ne sont jamais comblés.';

  @override
  String get observedDate => 'Date';

  @override
  String get observedMax => 'Maximum';

  @override
  String get observedMin => 'Minimum';

  @override
  String get precipTitle => 'Précipitations';

  @override
  String get precipGe1 => '≥ 1 mm';

  @override
  String get precipGe10 => '≥ 10 mm';

  @override
  String get precipNote =>
      'Fraction des membres utilisables avec une précipitation journalière cumulée égale ou supérieure au seuil.';

  @override
  String get day => 'Jour';

  @override
  String get date => 'Date';

  @override
  String get model => 'Modèle';

  @override
  String get rawBanner =>
      'Prévision d\'ensemble brute : non corrigée des biais et non calibrée. Aucune métrique de vérification n\'est publiée avant le seuil des 15 dates d\'émission.';

  @override
  String get attributionTitle => 'Données et attribution';

  @override
  String get attributionObserved =>
      'Séries observées : Servicio Meteorológico Nacional, archivées telles que servies ; les trous restent null et ne sont jamais comblés.';

  @override
  String get attributionNote =>
      'Les lignes d\'attribution sont reproduites telles quelles comme l\'exigent leurs licences ; seule l\'explication environnante est traduite.';

  @override
  String get aboutTitle => 'À propos / État';

  @override
  String get aboutWhatTitle => 'Ce que montre cette app';

  @override
  String get aboutWhat =>
      'PRISMA publie, pour 19 stations en Argentine, la prévision probabiliste brute de deux ensembles (ECMWF IFS et GFS) jusqu\'à 15 jours de prévision, ainsi que les températures maximales et minimales observées par le SMN sur les 30 derniers jours. L\'app ne lit que des fichiers statiques publiés sur GitHub Pages : il n\'y a ni serveur ni API.';

  @override
  String get aboutNoSkillTitle => 'Aucune métrique de skill';

  @override
  String get aboutNoSkill =>
      'L\'app n\'affiche ni CRPS, ni CRPSS, ni score de Brier, ni fiabilité, ni couverture, ni classement. Ces chiffres ne sont pas publiés avant le seuil des 15 dates d\'émission.';

  @override
  String get aboutStatusTitle => 'État des données';

  @override
  String get aboutSourcesTitle => 'Sources et licences';

  @override
  String get aboutDataset => 'Jeu de données';

  @override
  String get aboutSmnSnapshot => 'Instantané SMN (regtemp)';

  @override
  String get aboutRegion => 'Région';

  @override
  String get aboutSchema => 'Schéma';

  @override
  String get statusForecasts =>
      'Membres d\'ensemble bruts : non corrigés des biais, non calibrés et sans contrôle de qualité au-delà du flag de qualité de la source.';

  @override
  String get statusVerification =>
      'Aucun résultat de vérification (CRPS, CRPSS, Brier, fiabilité, couverture, classement) n\'est publié avant le seuil des 15 dates d\'émission dans docs/EVALUATION_PROTOCOL.md.';

  @override
  String get statusObservations =>
      'L\'instantané SMN regtemp est archivé tel que servi ; les trous restent null et ne sont jamais comblés. La règle de précédence des produits du 2026-11-14 s\'applique (regtemp primaire).';

  @override
  String get aboutMachineTranslations =>
      'Les traductions autres que l\'anglais sont générées par machine ; les corrections et améliorations sont les bienvenues.';

  @override
  String get languageLabel => 'Langue';

  @override
  String leadDay(int lead) {
    return '+$lead d';
  }

  @override
  String errorTitle(String document) {
    return 'Impossible de lire $document';
  }

  @override
  String schemaUnsupported(String version) {
    return 'La version de schéma \"$version\" n\'est pas prise en charge par cette app (attendu 1.0). Mettez à jour l\'app ou l\'export.';
  }

  @override
  String parseError(String document, String detail) {
    return 'Le document $document n\'est pas au format attendu : $detail';
  }

  @override
  String networkError(String document, String detail) {
    return 'Impossible de télécharger $document : $detail';
  }

  @override
  String httpError(int status, String document) {
    return 'La source de données a renvoyé HTTP $status pour $document.';
  }

  @override
  String invalidJson(String document, String detail) {
    return 'JSON invalide dans $document : $detail';
  }

  @override
  String get modelsNonText =>
      'Le champ \"models\" contient une valeur non textuelle.';

  @override
  String fieldNotObject(String field) {
    return 'Le champ \"$field\" n\'est pas un objet JSON.';
  }

  @override
  String fieldNotArray(String field) {
    return 'Le champ \"$field\" n\'est pas un tableau JSON.';
  }

  @override
  String missingTextField(String field) {
    return 'Champ texte \"$field\" manquant ou il n\'est pas une chaîne.';
  }

  @override
  String missingIntegerField(String field) {
    return 'Entier \"$field\" manquant ou ce n\'est pas un nombre.';
  }

  @override
  String notNumericField(String field) {
    return 'Le champ \"$field\" n\'est pas numérique.';
  }

  @override
  String missingSchemaVersion(String document) {
    return 'Champ schema_version manquant dans $document.';
  }

  @override
  String stationCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count stations',
      one: '$count station',
    );
    return '$_temp0';
  }

  @override
  String get stationsViewList => 'Liste';

  @override
  String get stationsViewMap => 'Carte';

  @override
  String get stationsViewForecast => 'Voir la prevision';

  @override
  String get mapLegend => 'Legende';

  @override
  String get mapReportProblem => 'Signaler un probleme de carte';

  @override
  String get mapTilesFailed =>
      'Impossible de charger les tuiles de la carte. Les stations sont affichees sur un fond neutre.';

  @override
  String get aboutMapTilesTitle => 'Tuiles de la carte';

  @override
  String get aboutMapTilesNote =>
      'La carte charge ses tuiles directement depuis les serveurs OpenStreetMap.';
}
