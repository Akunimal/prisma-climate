// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Italian (`it`).
class AppLocalizationsIt extends AppLocalizations {
  AppLocalizationsIt([String locale = 'it']) : super(locale);

  @override
  String get appTitle => 'PRISMA · Previsione per stazione';

  @override
  String get appTagline =>
      'Ensamble grezzo di Open-Meteo (GFS e ECMWF IFS) per oltre 140 stazioni nel mondo.';

  @override
  String get tabStations => 'Stazioni';

  @override
  String get tabForecast => 'Previsioni';

  @override
  String get tabSkill => 'Skill';

  @override
  String get tabAbout => 'Informazioni / Stato';

  @override
  String get searchHint => 'Cerca stazioni o luoghi';

  @override
  String get searchNoResults => 'Nessuna stazione corrisponde alla ricerca.';

  @override
  String get stationsIntro =>
      'Scegli una stazione per vedere la sua previsione.';

  @override
  String get clearSearch => 'Cancella';

  @override
  String get retry => 'Riprova';

  @override
  String get loading => 'Caricamento dati…';

  @override
  String get labelIssue => 'Emissione';

  @override
  String get labelExported => 'Esportato';

  @override
  String get labelSmn => 'Osservazioni SMN';

  @override
  String get labelClimateZone => 'Zona climatica';

  @override
  String get labelCoordinates => 'Coordinate';

  @override
  String get argentinaTimeNote => 'Ora argentina (UTC−3)';

  @override
  String get variableT2mMax => 'Massima giornaliera (t2m_max)';

  @override
  String get variableT2mMin => 'Minima giornaliera (t2m_min)';

  @override
  String get variablePrecip => 'Precipitazione (frazione di membri)';

  @override
  String get legendBand1090 => 'Fascia 10–90 %';

  @override
  String get legendBand2575 => 'Fascia 25–75 %';

  @override
  String get legendMedian => 'Mediana';

  @override
  String get legendClimatology => 'Intervallo normale';

  @override
  String get legendModelsNeverPooled =>
      'Ogni modello conserva i propri membri e le proprie percentili; non vengono mai uniti.';

  @override
  String get legendLeadAxis => 'Giorno di previsione';

  @override
  String get noData => 'nessun dato';

  @override
  String get missingMembersTitle => 'Nessun dato';

  @override
  String missingMembers(int members, int nominal) {
    return 'nessun dato ($members/$nominal membri)';
  }

  @override
  String get observedTitle => 'Osservato SMN — ultimi 30 giorni';

  @override
  String get observedNote =>
      'Valori archiviati come serviti dal SMN; i buchi restano null e non vengono mai riempiti.';

  @override
  String get observedDate => 'Data';

  @override
  String get observedMax => 'Massima';

  @override
  String get observedMin => 'Minima';

  @override
  String get precipTitle => 'Precipitazioni';

  @override
  String get precipGe1 => '≥ 1 mm';

  @override
  String get precipGe10 => '≥ 10 mm';

  @override
  String get precipNote =>
      'Frazione di membri utilizzabili con precipitazione giornaliera accumulata pari o sopra la soglia.';

  @override
  String get day => 'Giorno';

  @override
  String get date => 'Data';

  @override
  String get model => 'Modello';

  @override
  String get rawBanner =>
      'Previsione di ensamble grezza: senza correzione del bias e non calibrata. Nessuna metrica di verifica viene pubblicata prima della soglia delle 15 date di emissione.';

  @override
  String get attributionTitle => 'Dati e attribuzione';

  @override
  String get attributionObserved =>
      'Serie osservate: Servicio Meteorológico Nacional, archiviate come servite; i buchi restano null e non vengono mai riempiti.';

  @override
  String get attributionNote =>
      'Le righe di attribuzione sono riprodotte testualmente come richiedono le loro licenze; solo la spiegazione circostante viene tradotta.';

  @override
  String get aboutTitle => 'Informazioni / Stato';

  @override
  String get aboutWhatTitle => 'Cosa mostra questa app';

  @override
  String get aboutWhat =>
      'PRISMA pubblica, per oltre 140 stazioni in tutti i continenti, la previsione probabilistica grezza di due ensambles (ECMWF IFS e GFS) fino a 15 giorni di previsione, oltre alle osservazioni dei servizi meteorologici nazionali e della rete globale METAR. L\'app legge solo file statici pubblicati su GitHub Pages: non c\'è nessun server né API.';

  @override
  String get aboutNoSkillTitle => 'Metriche di skill operative';

  @override
  String get aboutNoSkill =>
      'I risultati di verifica operativi (CRPS, CRPSS, Brier, affidabilità, copertura, classifica) non sono pubblicati prima della soglia delle 15 date di emissione. La schermata Skill mostra solo punteggi di calibrazione etichettati hindcast, da un replay storico; non vengono mai mescolati con l\'archivio operativo.';

  @override
  String get skillTitle => 'Skill di calibrazione (hindcast)';

  @override
  String get skillHindcastBanner =>
      'Solo hindcast: questi punteggi provengono da un replay storico contro osservazioni archiviate, non dall\'archivio delle previsioni live. Non vengono mai mescolati con la verifica operativa.';

  @override
  String get skillUnavailable =>
      'Non è ancora dispon nessun run di calibrazione hindcast.';

  @override
  String get skillLabel => 'Etichetta';

  @override
  String get skillMeanEmos => 'CRPSS medio (EMOS vs grezzo)';

  @override
  String get skillMeanQm => 'CRPSS medio (QM vs grezzo)';

  @override
  String skillCellsCount(int sufficient, int total) {
    return '$sufficient celle su $total con dati di addestramento sufficienti';
  }

  @override
  String get skillDidNotBeat =>
      'CRPSS medio ≤ 0: in questa finestra hindcast la calibrazione non ha battuto l\'ensemble grezzo.';

  @override
  String get skillProvider => 'Fornitore';

  @override
  String get skillWindow => 'Finestra';

  @override
  String get skillRetrieved => 'Recuperato';

  @override
  String get skillLeads => 'Giorni di previsione';

  @override
  String get skillMode => 'Modalità';

  @override
  String get skillGateTitle => 'Soglia operativa';

  @override
  String skillGateArchived(int archived, int required) {
    return 'Date di emissione archiviate: $archived su $required';
  }

  @override
  String get skillGateOpen =>
      'Soglia aperta — la classifica operativa può essere pubblicata.';

  @override
  String get skillGateClosed =>
      'Soglia chiusa — la classifica operativa non è pubblicata.';

  @override
  String get skillCellsTitle => 'Celle per stazione e giorno di previsione';

  @override
  String get skillCellStation => 'Stazione';

  @override
  String get comparatorTitle => 'Confronto delle fonti';

  @override
  String get comparatorNote =>
      'Percentili della massima giornaliera affiancati per modello (°C): p10–p90 · mediana. Mai uniti.';

  @override
  String get aboutStatusTitle => 'Stato dei dati';

  @override
  String get aboutSourcesTitle => 'Fonti e licenze';

  @override
  String get aboutDataset => 'Dataset';

  @override
  String get aboutSmnSnapshot => 'Istantanea SMN (regtemp)';

  @override
  String get aboutRegion => 'Regione';

  @override
  String get aboutSchema => 'Schema';

  @override
  String get statusForecasts =>
      'Membri di ensamble grezzi: senza correzione del bias, non calibrati e senza controllo di qualità oltre al flag di qualità della fonte.';

  @override
  String get statusVerification =>
      'Nessun risultato di verifica (CRPS, CRPSS, Brier, affidabilità, copertura, classifica) viene pubblicato prima della soglia delle 15 date di emissione in docs/EVALUATION_PROTOCOL.md.';

  @override
  String get statusObservations =>
      'L\'istantanea SMN regtemp è archiviata come servita; i buchi restano null e non vengono mai riempiti. Si applica la regola di precedenza dei prodotti del 2026-11-14 (regtemp primario).';

  @override
  String get aboutMachineTranslations =>
      'Le traduzioni diverse dall\'inglese sono generate automaticamente; correzioni e miglioramenti sono benvenuti.';

  @override
  String get languageLabel => 'Lingua';

  @override
  String leadDay(int lead) {
    return '+$lead d';
  }

  @override
  String errorTitle(String document) {
    return 'Impossibile leggere $document';
  }

  @override
  String schemaUnsupported(String version) {
    return 'La versione dello schema \"$version\" non è supportata da questa app (atteso 1.0). Aggiorna l\'app o l\'export.';
  }

  @override
  String parseError(String document, String detail) {
    return 'Il documento $document non è nel formato previsto: $detail';
  }

  @override
  String networkError(String document, String detail) {
    return 'Impossibile scaricare $document: $detail';
  }

  @override
  String httpError(int status, String document) {
    return 'La fonte dati ha restituito HTTP $status per $document.';
  }

  @override
  String invalidJson(String document, String detail) {
    return 'JSON non valido in $document: $detail';
  }

  @override
  String get modelsNonText =>
      'Il campo \"models\" contiene un valore non testuale.';

  @override
  String fieldNotObject(String field) {
    return 'Il campo \"$field\" non è un oggetto JSON.';
  }

  @override
  String fieldNotArray(String field) {
    return 'Il campo \"$field\" non è un array JSON.';
  }

  @override
  String missingTextField(String field) {
    return 'Campo testo \"$field\" mancante o non è una stringa.';
  }

  @override
  String missingIntegerField(String field) {
    return 'Intero \"$field\" mancante o non è un numero.';
  }

  @override
  String notNumericField(String field) {
    return 'Il campo \"$field\" non è numerico.';
  }

  @override
  String missingSchemaVersion(String document) {
    return 'Campo schema_version mancante in $document.';
  }

  @override
  String stationCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count stazioni',
      one: '$count stazione',
    );
    return '$_temp0';
  }

  @override
  String get stationsViewList => 'Elenco';

  @override
  String get stationsViewMap => 'Mappa';

  @override
  String get stationsViewForecast => 'Vedi previsione';

  @override
  String get mapLegend => 'Legenda';

  @override
  String get mapReportProblem => 'Segnala un problema della mappa';

  @override
  String get mapTilesFailed =>
      'Impossibile caricare le tessere della mappa. Le stazioni sono mostrate su sfondo neutro.';

  @override
  String get aboutMapTilesTitle => 'Tessere della mappa';

  @override
  String get aboutMapTilesNote =>
      'La mappa carica le sue tessere direttamente dai server OpenStreetMap.';

  @override
  String get searchStationsGroup => 'Stazioni';

  @override
  String get searchPlacesGroup => 'Luoghi';

  @override
  String get placesUnavailable =>
      'La ricerca dei luoghi non è disponibile al momento.';

  @override
  String nearestStation(String station) {
    return 'Stazione più vicina: $station';
  }

  @override
  String distanceKm(String km) {
    return 'Distanza: $km km';
  }

  @override
  String get nearestStationWarning =>
      'Nessuna stazione entro 100 km — la previsione è per la stazione più vicina, che potrebbe non rappresentare la tua posizione.';

  @override
  String get useMyLocation => 'Usa la mia posizione';

  @override
  String get locationDenied =>
      'Permesso di localizzazione negato. Cerca un luogo.';

  @override
  String get locationUnavailable =>
      'La localizzazione non è disponibile su questo dispositivo.';

  @override
  String get locationTimeout =>
      'Impossibile ottenere la tua posizione. Riprova o cerca un luogo.';

  @override
  String get yourLocation => 'La tua posizione';

  @override
  String get aboutPlacesTitle => 'Dati dei luoghi';

  @override
  String get aboutPlacesNote =>
      'I nomi dei luoghi provengono da GeoNames e sono usati solo per la ricerca su questo dispositivo.';

  @override
  String get aboutPrivacyTitle => 'Privacy';

  @override
  String get aboutPrivacyNote =>
      'La ricerca dei luoghi e la localizzazione restano su questo dispositivo; solo le tessere della mappa vengono richieste al fornitore della mappa.';
}
