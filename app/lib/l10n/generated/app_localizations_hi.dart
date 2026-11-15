// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Hindi (`hi`).
class AppLocalizationsHi extends AppLocalizations {
  AppLocalizationsHi([String locale = 'hi']) : super(locale);

  @override
  String get appTitle => 'PRISMA · स्टेशन के अनुसार पूर्वानुमान';

  @override
  String get appTagline =>
      'Open-Meteo का कच्चा एन्सेम्बल पूर्वानुमान (GFS और ECMWF IFS), अर्जेंटीना के 19 स्टेशनों के लिए।';

  @override
  String get tabStations => 'स्टेशन';

  @override
  String get tabForecast => 'पूर्वानुमान';

  @override
  String get tabSkill => 'स्किल';

  @override
  String get tabAbout => 'जानकारी / स्थिति';

  @override
  String get searchHint => 'स्टेशन या स्थान खोजें';

  @override
  String get searchNoResults => 'कोई स्टेशन खोज से मेल नहीं खाता।';

  @override
  String get stationsIntro => 'पूर्वानुमान देखने के लिए कोई स्टेशन चुनें।';

  @override
  String get clearSearch => 'साफ़ करें';

  @override
  String get retry => 'पुनः प्रयास';

  @override
  String get loading => 'डेटा लोड हो रहा है…';

  @override
  String get labelIssue => 'जारी समय';

  @override
  String get labelExported => 'निर्यात समय';

  @override
  String get labelSmn => 'SMN अवलोकन';

  @override
  String get labelClimateZone => 'जलवायु क्षेत्र';

  @override
  String get labelCoordinates => 'निर्देशांक';

  @override
  String get argentinaTimeNote => 'अर्जेंटीना समय (UTC−3)';

  @override
  String get variableT2mMax => 'दैनिक अधिकतम (t2m_max)';

  @override
  String get variableT2mMin => 'दैनिक न्यूनतम (t2m_min)';

  @override
  String get variablePrecip => 'वर्षा (सदस्य अंश)';

  @override
  String get legendBand1090 => '10–90% श्रेणी';

  @override
  String get legendBand2575 => '25–75% श्रेणी';

  @override
  String get legendMedian => 'माध्यिका';

  @override
  String get legendModelsNeverPooled =>
      'हर मॉडल अपने सदस्यों और अपने पर्सेंटाइल रखता है; उन्हें कभी मिलाया नहीं जाता।';

  @override
  String get legendLeadAxis => 'लीड दिवस';

  @override
  String get noData => 'कोई डेटा नहीं';

  @override
  String get missingMembersTitle => 'कोई डेटा नहीं';

  @override
  String missingMembers(int members, int nominal) {
    return 'कोई डेटा नहीं ($members/$nominal सदस्य)';
  }

  @override
  String get observedTitle => 'SMN अवलोकन — पिछले 30 दिन';

  @override
  String get observedNote =>
      'SMN द्वारा प्रदान किए गए अनुसार संग्रहित मान; अंतराल null रहते हैं और कभी भरे नहीं जाते।';

  @override
  String get observedDate => 'तिथि';

  @override
  String get observedMax => 'अधिकतम';

  @override
  String get observedMin => 'न्यूनतम';

  @override
  String get precipTitle => 'वर्षा';

  @override
  String get precipGe1 => '≥ 1 mm';

  @override
  String get precipGe10 => '≥ 10 mm';

  @override
  String get precipNote =>
      'उपयोगी सदस्यों में से उनका अंश जिनकी दैनिक संचयी वर्षा सीमा या उससे अधिक है।';

  @override
  String get day => 'दिन';

  @override
  String get date => 'तिथि';

  @override
  String get model => 'मॉडल';

  @override
  String get rawBanner =>
      'कच्चा एन्सेम्बल पूर्वानुमान: बायस सुधारित नहीं, कैलिब्रेट नहीं। 15 जारी तिथियों के गेट से पहले कोई सत्यापन मेट्रिक प्रकाशित नहीं होती।';

  @override
  String get attributionTitle => 'डेटा और एट्रिब्यूशन';

  @override
  String get attributionObserved =>
      'अवलोकित श्रृंखलाएँ: Servicio Meteorológico Nacional, प्रदान किए गए अनुसार संग्रहित; अंतराल null रहते हैं और कभी भरे नहीं जाते।';

  @override
  String get attributionNote =>
      'एट्रिब्यूशन पंक्तियाँ उनके लाइसेंस की आवश्यकता के अनुसार शब्दशः दोहराई जाती हैं; केवल आसपास की व्याख्या अनूदित होती है।';

  @override
  String get aboutTitle => 'जानकारी / स्थिति';

  @override
  String get aboutWhatTitle => 'यह ऐप क्या दिखाता है';

  @override
  String get aboutWhat =>
      'PRISMA अर्जेंटीना के 19 स्टेशनों के लिए दो एन्सेम्बल (ECMWF IFS और GFS) का कच्चा संभाव्य पूर्वानुमान 15 दिनों तक, साथ ही पिछले 30 दिनों में SMN द्वारा अवलोकित दैनिक अधिकतम और न्यूनतम तापमान प्रकाशित करता है। ऐप केवल GitHub Pages पर प्रकाशित स्थिर फ़ाइलें पढ़ता है: कोई सर्वर या API नहीं है।';

  @override
  String get aboutNoSkillTitle => 'संचालन सत्यापन मेट्रिक';

  @override
  String get aboutNoSkill =>
      'संचालन सत्यापन परिणाम (CRPS, CRPSS, Brier, विश्वसनीयता, कवरेज, लीडरबोर्ड) 15 जारी तिथियों के गेट से पहले प्रकाशित नहीं होते। स्किल स्क्रीन केवल hindcast-लेबल वाले ऐतिहासिक रीप्ले कैलिब्रेशन स्कोर दिखाती है; उन्हें कभी संचालन आर्काइव के साथ नहीं मिलाया जाता।';

  @override
  String get skillTitle => 'कैलिब्रेशन स्किल (hindcast)';

  @override
  String get skillHindcastBanner =>
      'केवल hindcast: ये स्कोर संग्रहित अवलोकनों के खिलाफ ऐतिहासिक रीप्ले से आते हैं, लाइव पूर्वानुमान आर्काइव से नहीं। उन्हें कभी संचालन सत्यापन के साथ नहीं मिलाया जाता।';

  @override
  String get skillUnavailable =>
      'अभी कोई hindcast कैलिब्रेशन रन उपलब्ध नहीं है।';

  @override
  String get skillLabel => 'लेबल';

  @override
  String get skillMeanEmos => 'मीन CRPSS (EMOS बनाम कच्चा)';

  @override
  String get skillMeanQm => 'मीन CRPSS (QM बनाम कच्चा)';

  @override
  String skillCellsCount(int sufficient, int total) {
    return '$total में से $sufficient कोशिकाओं में पर्याप्त प्रशिक्षण डेटा';
  }

  @override
  String get skillDidNotBeat =>
      'मीन CRPSS ≤ 0: इस hindcast विंडो में कैलिब्रेशन कच्चे एन्सेम्बल को नहीं हरा पाया।';

  @override
  String get skillProvider => 'प्रदाता';

  @override
  String get skillWindow => 'विंडो';

  @override
  String get skillRetrieved => 'प्राप्त';

  @override
  String get skillLeads => 'लीड';

  @override
  String get skillMode => 'मोड';

  @override
  String get skillGateTitle => 'संचालन गेट';

  @override
  String skillGateArchived(int archived, int required) {
    return 'संग्रहित जारी तिथियाँ: $archived / $required';
  }

  @override
  String get skillGateOpen =>
      'गेट खुला — संचालन लीडरबोर्ड प्रकाशित किया जा सकता है।';

  @override
  String get skillGateClosed =>
      'गेट बंद — संचालन लीडरबोर्ड प्रकाशित नहीं होता।';

  @override
  String get skillCellsTitle => 'स्टेशन और लीड के अनुसार कोशिकाएँ';

  @override
  String get skillCellStation => 'स्टेशन';

  @override
  String get comparatorTitle => 'स्रोत तुलना';

  @override
  String get comparatorNote =>
      'प्रति मॉडल दैनिक अधिकतम पर्सेंटाइल साथ-साथ (°C): p10–p90 · माध्यिका। कभी मिलाए नहीं जाते।';

  @override
  String get aboutStatusTitle => 'डेटा की स्थिति';

  @override
  String get aboutSourcesTitle => 'स्रोत और लाइसेंस';

  @override
  String get aboutDataset => 'डेटासेट';

  @override
  String get aboutSmnSnapshot => 'SMN स्नैपशॉट (regtemp)';

  @override
  String get aboutRegion => 'क्षेत्र';

  @override
  String get aboutSchema => 'स्कीमा';

  @override
  String get statusForecasts =>
      'कच्चे एन्सेम्बल सदस्य: बायस सुधारित नहीं, कैलिब्रेट नहीं, और स्रोत क्वालिटी फ़्लैग के अलावा गुणवत्ता नियंत्रण नहीं।';

  @override
  String get statusVerification =>
      'docs/EVALUATION_PROTOCOL.md में 15 जारी तिथियों के गेट से पहले कोई सत्यापन परिणाम (CRPS, CRPSS, Brier, विश्वसनीयता, कवरेज, लीडरबोर्ड) प्रकाशित नहीं होते।';

  @override
  String get statusObservations =>
      'SMN regtemp स्नैपशॉट प्रदान किए गए अनुसार संग्रहित है; अंतराल null रहते हैं और कभी भरे नहीं जाते। 2026-11-14 का उत्पाद प्राथमिकता नियम लागू है (regtemp प्राथमिक)।';

  @override
  String get aboutMachineTranslations =>
      'अंग्रेज़ी के अलावा अन्य अनुवाद मशीन से बने हैं; सुधार और सुझाव स्वागत हैं।';

  @override
  String get languageLabel => 'भाषा';

  @override
  String leadDay(int lead) {
    return '+$lead d';
  }

  @override
  String errorTitle(String document) {
    return '$document पढ़ा नहीं जा सका';
  }

  @override
  String schemaUnsupported(String version) {
    return 'स्कीमा संस्करण \"$version\" इस ऐप द्वारा समर्थित नहीं है (अपेक्षित 1.0)। ऐप या एक्सपोर्ट अपडेट करें।';
  }

  @override
  String parseError(String document, String detail) {
    return 'दस्तावेज़ $document अपेक्षित प्रारूप में नहीं है: $detail';
  }

  @override
  String networkError(String document, String detail) {
    return '$document डाउनलोड नहीं हो सका: $detail';
  }

  @override
  String httpError(int status, String document) {
    return 'डेटा स्रोत ने $document के लिए HTTP $status लौटाया।';
  }

  @override
  String invalidJson(String document, String detail) {
    return '$document में अमान्य JSON: $detail';
  }

  @override
  String get modelsNonText => '\"models\" फ़ील्ड में गैर-पाठ मान है।';

  @override
  String fieldNotObject(String field) {
    return 'फ़ील्ड \"$field\" JSON ऑब्जेक्ट नहीं है।';
  }

  @override
  String fieldNotArray(String field) {
    return 'फ़ील्ड \"$field\" JSON सरणी नहीं है।';
  }

  @override
  String missingTextField(String field) {
    return 'पाठ फ़ील्ड \"$field\" अनुपस्थित है या वह स्ट्रिंग नहीं है।';
  }

  @override
  String missingIntegerField(String field) {
    return 'पूर्णांक \"$field\" अनुपस्थित है या वह संख्या नहीं है।';
  }

  @override
  String notNumericField(String field) {
    return 'फ़ील्ड \"$field\" संख्यात्मक नहीं है।';
  }

  @override
  String missingSchemaVersion(String document) {
    return '$document में schema_version फ़ील्ड अनुपस्थित है।';
  }

  @override
  String stationCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count स्टेशन',
    );
    return '$_temp0';
  }

  @override
  String get stationsViewList => 'सूची';

  @override
  String get stationsViewMap => 'मानचित्र';

  @override
  String get stationsViewForecast => 'पूर्वानुमान देखें';

  @override
  String get mapLegend => 'लीजेंड';

  @override
  String get mapReportProblem => 'मानचित्र समस्या रिपोर्ट करें';

  @override
  String get mapTilesFailed =>
      'मानचित्र टाइल लोड नहीं हो सके। न्यूट्रल पृष्ठभूमि पर स्टेशन दिखाए जा रहे हैं।';

  @override
  String get aboutMapTilesTitle => 'मानचित्र टाइल';

  @override
  String get aboutMapTilesNote =>
      'मानचित्र सीधे OpenStreetMap सर्वर से टाइल लोड करता है।';

  @override
  String get searchStationsGroup => 'स्टेशन';

  @override
  String get searchPlacesGroup => 'स्थान';

  @override
  String get placesUnavailable => 'स्थान खोज अभी उपलब्ध नहीं है।';

  @override
  String nearestStation(String station) {
    return 'निकटतम स्टेशन: $station';
  }

  @override
  String distanceKm(String km) {
    return 'दूरी: $km km';
  }

  @override
  String get nearestStationWarning =>
      '100 km के भीतर कोई स्टेशन नहीं है — पूर्वानुमान निकटतम स्टेशन का है, जो आपके स्थान को नहीं दर्शा सकता।';

  @override
  String get useMyLocation => 'मेरा स्थान उपयोग करें';

  @override
  String get locationDenied => 'स्थान की अनुमति अस्वीकृत। कृपया स्थान खोजें।';

  @override
  String get locationUnavailable => 'इस डिवाइस पर स्थान उपलब्ध नहीं है।';

  @override
  String get locationTimeout =>
      'आपका स्थान प्राप्त नहीं हो सका। पुनः प्रयास करें या स्थान खोजें।';

  @override
  String get yourLocation => 'आपका स्थान';

  @override
  String get aboutPlacesTitle => 'स्थान डेटा';

  @override
  String get aboutPlacesNote =>
      'स्थान नाम GeoNames से आते हैं और केवल इस डिवाइस पर खोज के लिए उपयोग होते हैं।';

  @override
  String get aboutPrivacyTitle => 'गोपनीयता';

  @override
  String get aboutPrivacyNote =>
      'स्थान खोज और स्थान इस डिवाइस पर ही रहते हैं; केवल मानचित्र टाइल मानचित्र प्रदाता से अनुरोधित होते हैं।';
}
