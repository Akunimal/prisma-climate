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
      'अर्जेंटीना के 19 स्टेशनों के लिए Open-Meteo का कच्चा एन्सेम्बल (GFS और ECMWF IFS)।';

  @override
  String get tabStations => 'स्टेशन';

  @override
  String get tabForecast => 'पूर्वानुमान';

  @override
  String get tabAbout => 'जानकारी / स्थिति';

  @override
  String get searchHint => 'स्टेशन खोजें';

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
  String get labelIssue => 'जारी';

  @override
  String get labelExported => 'निर्यात';

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
      'हर मॉडल अपने सदस्यों और अपने पर्सेंटाइल रखता है; उन्हें कभी नहीं मिलाया जाता।';

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
      'उपयोगी सदस्यों का वह अंश जिनकी दैनिक संचित वर्षा सीमा के बराबर या उससे अधिक है।';

  @override
  String get day => 'दिन';

  @override
  String get date => 'तिथि';

  @override
  String get model => 'मॉडल';

  @override
  String get rawBanner =>
      'कच्चा एन्सेम्बल पूर्वानुमान: पूर्वाग्रह-सुधार नहीं, कैलिब्रेशन नहीं। 15 जारी तिथियों के द्वार से पहले कोई सत्यापन मेट्रिक प्रकाशित नहीं होता।';

  @override
  String get attributionTitle => 'डेटा और श्रेय';

  @override
  String get attributionObserved =>
      'अवलोकित श्रृंखलाएँ: Servicio Meteorológico Nacional, प्रदान किए गए अनुसार संग्रहित; अंतराल null रहते हैं और कभी भरे नहीं जाते।';

  @override
  String get attributionNote =>
      'श्रेय पंक्तियाँ उनकी लाइसेंस की आवश्यकता के अनुसार शब्दशः दोहराई जाती हैं; केवल आसपास की व्याख्या अनूदित की जाती है।';

  @override
  String get aboutTitle => 'जानकारी / स्थिति';

  @override
  String get aboutWhatTitle => 'यह ऐप क्या दिखाता है';

  @override
  String get aboutWhat =>
      'PRISMA अर्जेंटीना के 19 स्टेशनों के लिए दो एन्सेम्बल (ECMWF IFS और GFS) का 15 दिन आगे तक कच्चा संभाव्य पूर्वानुमान प्रकाशित करता है, साथ ही पिछले 30 दिनों में SMN द्वारा अवलोकित दैनिक अधिकतम और न्यूनतम तापमान। ऐप केवल GitHub Pages पर प्रकाशित स्थिर फ़ाइलें पढ़ता है: कोई सर्वर नहीं, कोई API नहीं।';

  @override
  String get aboutNoSkillTitle => 'कोई स्किल मेट्रिक नहीं';

  @override
  String get aboutNoSkill =>
      'ऐप CRPS, CRPSS, Brier, विश्वसनीयता, कवरेज या लीडरबोर्ड नहीं दिखाता। ये संख्याएँ 15 जारी तिथियों के द्वार से पहले प्रकाशित नहीं होतीं।';

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
      'कच्चे एन्सेम्बल सदस्य: पूर्वाग्रह-सुधार नहीं, कैलिब्रेशन नहीं, और स्रोत के गुणवत्ता फ़्लैग से आगे गुणवत्ता नियंत्रण नहीं।';

  @override
  String get statusVerification =>
      'docs/EVALUATION_PROTOCOL.md में 15 जारी तिथियों के द्वार से पहले कोई सत्यापन परिणाम (CRPS, CRPSS, Brier, विश्वसनीयता, कवरेज, लीडरबोर्ड) प्रकाशित नहीं होता।';

  @override
  String get statusObservations =>
      'SMN regtemp स्नैपशॉट प्रदान किए गए अनुसार संग्रहित है; अंतराल null रहते हैं और कभी भरे नहीं जाते। 2026-11-14 का उत्पाद प्राथमिकता नियम लागू है (regtemp प्राथमिक)।';

  @override
  String get aboutMachineTranslations =>
      'अंग्रेज़ी के अलावा की अन्य अनुवाद मशीन से बने हैं; सुधार और बेहतरी का स्वागत है।';

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
    return 'पाठ फ़ील्ड \"$field\" अनुपलब्ध है या वह स्ट्रिंग नहीं है।';
  }

  @override
  String missingIntegerField(String field) {
    return 'पूर्णांक \"$field\" अनुपलब्ध है या वह संख्या नहीं है।';
  }

  @override
  String notNumericField(String field) {
    return 'फ़ील्ड \"$field\" संख्यात्मक नहीं है।';
  }

  @override
  String missingSchemaVersion(String document) {
    return '$document में schema_version फ़ील्ड अनुपलब्ध है।';
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
}
