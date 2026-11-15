// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Japanese (`ja`).
class AppLocalizationsJa extends AppLocalizations {
  AppLocalizationsJa([String locale = 'ja']) : super(locale);

  @override
  String get appTitle => 'PRISMA · 観測所別の予報';

  @override
  String get appTagline =>
      'Open-Meteo の未校正アンサンブル（GFS と ECMWF IFS）、アルゼンチンの 19 観測所。';

  @override
  String get tabStations => '観測所';

  @override
  String get tabForecast => '予報';

  @override
  String get tabSkill => 'スキル';

  @override
  String get tabAbout => '情報 / 状態';

  @override
  String get searchHint => '観測所または場所を検索';

  @override
  String get searchNoResults => '検索に一致する観測所がありません。';

  @override
  String get stationsIntro => '観測所を選ぶとその予報が表示されます。';

  @override
  String get clearSearch => 'クリア';

  @override
  String get retry => '再試行';

  @override
  String get loading => 'データを読み込み中…';

  @override
  String get labelIssue => '発表時刻';

  @override
  String get labelExported => 'エクスポート時刻';

  @override
  String get labelSmn => 'SMN 観測';

  @override
  String get labelClimateZone => '気候区分';

  @override
  String get labelCoordinates => '座標';

  @override
  String get argentinaTimeNote => 'アルゼンチン時間（UTC−3）';

  @override
  String get variableT2mMax => '日最高温（t2m_max）';

  @override
  String get variableT2mMin => '日最低温（t2m_min）';

  @override
  String get variablePrecip => '降水量（メンバーの割合）';

  @override
  String get legendBand1090 => '10–90% 帯';

  @override
  String get legendBand2575 => '25–75% 帯';

  @override
  String get legendMedian => '中央値';

  @override
  String get legendModelsNeverPooled =>
      '各モデルはそれぞれのメンバーとそれぞれのパーセンタイルを保持し、混ぜ合わせることは決してありません。';

  @override
  String get legendLeadAxis => '予報日数';

  @override
  String get noData => 'データなし';

  @override
  String get missingMembersTitle => 'データなし';

  @override
  String missingMembers(int members, int nominal) {
    return 'データなし（$members/$nominal メンバー）';
  }

  @override
  String get observedTitle => 'SMN 観測 — 過去 30 日';

  @override
  String get observedNote => 'SMN が提供した通りにアーカイブした値；欠測は null のままで、決して補完しません。';

  @override
  String get observedDate => '日付';

  @override
  String get observedMax => '最高';

  @override
  String get observedMin => '最低';

  @override
  String get precipTitle => '降水';

  @override
  String get precipGe1 => '≥ 1 mm';

  @override
  String get precipGe10 => '≥ 10 mm';

  @override
  String get precipNote => '利用可能なメンバーのうち、日累積降水がしきい値以上であるものの割合。';

  @override
  String get day => '日';

  @override
  String get date => '日付';

  @override
  String get model => 'モデル';

  @override
  String get rawBanner =>
      '未校正アンサンブル予報：バイアス補正なし・キャリブレーションなし。15 発表日のゲートを前にして検証指標は一切公開しません。';

  @override
  String get attributionTitle => 'データと出典';

  @override
  String get attributionObserved =>
      '観測系列：Servicio Meteorológico Nacional、提供されたとおりにアーカイブ；欠測は null のままで、決して補完しません。';

  @override
  String get attributionNote => '帰属行はライセンスの要求に従って逐語的に複製し、周囲の説明のみ翻訳します。';

  @override
  String get aboutTitle => '情報 / 状態';

  @override
  String get aboutWhatTitle => 'このアプリが表示するもの';

  @override
  String get aboutWhat =>
      'PRISMA は、アルゼンチンの 19 観測所について、2 つのアンサンブル（ECMWF IFS と GFS）の未校正確率予報を最大 15 日先まで、さらに SMN が過去 30 日間に観測した日最高・日最低気温を公開します。アプリは GitHub Pages 上の静的ファイルのみを読み込みます：サーバーも API もありません。';

  @override
  String get aboutNoSkillTitle => '運用検証指標';

  @override
  String get aboutNoSkill =>
      '運用検証結果（CRPS、CRPSS、Brier、信頼性、被覆率、リーダーボード）は 15 発表日のゲートを前にして公開されません。スキル画面は hindcast ラベル付きの履歴リプレイ校準スコアのみを表示し、運用アーカイブと混ぜることは決してありません。';

  @override
  String get skillTitle => '校準スキル（hindcast）';

  @override
  String get skillHindcastBanner =>
      'hindcast のみ：これらのスコアはアーカイブ観測に対する履歴リプレイ由来で、ライブ予報アーカイブ由来ではありません。運用検証と混ぜることは決してありません。';

  @override
  String get skillUnavailable => '利用可能な hindcast 校準ランはまだありません。';

  @override
  String get skillLabel => 'ラベル';

  @override
  String get skillMeanEmos => '平均 CRPSS（EMOS 対 生）';

  @override
  String get skillMeanQm => '平均 CRPSS（QM 対 生）';

  @override
  String skillCellsCount(int sufficient, int total) {
    return '訓練データが十分なセル $sufficient / $total';
  }

  @override
  String get skillDidNotBeat =>
      '平均 CRPSS ≤ 0：この hindcast 窗で校準は生アンサンブルを上回りませんでした。';

  @override
  String get skillProvider => 'プロバイダ';

  @override
  String get skillWindow => '期間';

  @override
  String get skillRetrieved => '取得日時';

  @override
  String get skillLeads => '予報日数';

  @override
  String get skillMode => 'モード';

  @override
  String get skillGateTitle => '運用ゲート';

  @override
  String skillGateArchived(int archived, int required) {
    return 'アーカイブ済み発表日：$archived / $required';
  }

  @override
  String get skillGateOpen => 'ゲート開放 — 運用リーダーボードを公開できます。';

  @override
  String get skillGateClosed => 'ゲートクローズ — 運用リーダーボードは公開されません。';

  @override
  String get skillCellsTitle => '観測所・予報日数別のセル';

  @override
  String get skillCellStation => '観測所';

  @override
  String get comparatorTitle => 'ソース比較';

  @override
  String get comparatorNote =>
      'モデルごとの日最高温パーセンタイルを横並び（°C）：p10–p90 · 中央値。混ぜ合わせることは決してありません。';

  @override
  String get aboutStatusTitle => 'データの状態';

  @override
  String get aboutSourcesTitle => '出典とライセンス';

  @override
  String get aboutDataset => 'データセット';

  @override
  String get aboutSmnSnapshot => 'SMN スナップショット（regtemp）';

  @override
  String get aboutRegion => '地域';

  @override
  String get aboutSchema => 'スキーマ';

  @override
  String get statusForecasts =>
      '未校正アンサンブルメンバー：バイアス補正なし、キャリブレーションなし、元データの品質フラグを超えた品質管理もなし。';

  @override
  String get statusVerification =>
      '15 発表日のゲート（docs/EVALUATION_PROTOCOL.md）を前にして、検証結果（CRPS、CRPSS、Brier、信頼性、被覆率、リーダーボード）は公開されません。';

  @override
  String get statusObservations =>
      'SMN regtemp スナップショットは提供されたとおりにアーカイブ；欠測は null のままで、決して補完しません。2026-11-14 の製品優先ルールが適用されます（regtemp が優先）。';

  @override
  String get aboutMachineTranslations => '英語以外の翻訳は機械生成です。訂正・改善を歓迎します。';

  @override
  String get languageLabel => '言語';

  @override
  String leadDay(int lead) {
    return '+$lead d';
  }

  @override
  String errorTitle(String document) {
    return '$document を読み取れませんでした';
  }

  @override
  String schemaUnsupported(String version) {
    return 'スキーマバージョン「$version」はこのアプリではサポートされていません（期待値 1.0）。アプリまたはエクスポートを更新してください。';
  }

  @override
  String parseError(String document, String detail) {
    return 'ドキュメント $document が期待した形式ではありません：$detail';
  }

  @override
  String networkError(String document, String detail) {
    return '$document をダウンロードできませんでした：$detail';
  }

  @override
  String httpError(int status, String document) {
    return 'データソースが $document に対して HTTP $status を返しました。';
  }

  @override
  String invalidJson(String document, String detail) {
    return '$document の JSON が無効です：$detail';
  }

  @override
  String get modelsNonText => '「models」フィールドにテキスト以外の値が含まれています。';

  @override
  String fieldNotObject(String field) {
    return 'フィールド「$field」は JSON オブジェクトではありません。';
  }

  @override
  String fieldNotArray(String field) {
    return 'フィールド「$field」は JSON 配列ではありません。';
  }

  @override
  String missingTextField(String field) {
    return 'テキストフィールド「$field」が欠落しているか、文字列ではありません。';
  }

  @override
  String missingIntegerField(String field) {
    return '整数「$field」が欠落しているか、数値ではありません。';
  }

  @override
  String notNumericField(String field) {
    return 'フィールド「$field」は数値ではありません。';
  }

  @override
  String missingSchemaVersion(String document) {
    return '$document に schema_version フィールドがありません。';
  }

  @override
  String stationCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count ステーション',
    );
    return '$_temp0';
  }

  @override
  String get stationsViewList => 'リスト';

  @override
  String get stationsViewMap => '地図';

  @override
  String get stationsViewForecast => '予報を表示';

  @override
  String get mapLegend => '凡例';

  @override
  String get mapReportProblem => '地図の問題を報告';

  @override
  String get mapTilesFailed => '地図タイルを読み込めませんでした。中性背景に観測点を表示しています。';

  @override
  String get aboutMapTilesTitle => '地図タイル';

  @override
  String get aboutMapTilesNote => '地図は OpenStreetMap サーバーから直接タイルを読み込みます。';

  @override
  String get searchStationsGroup => '観測所';

  @override
  String get searchPlacesGroup => '場所';

  @override
  String get placesUnavailable => '現在、場所検索を利用できません。';

  @override
  String nearestStation(String station) {
    return '最寄りの観測所：$station';
  }

  @override
  String distanceKm(String km) {
    return '距離：$km km';
  }

  @override
  String get nearestStationWarning =>
      '100 km 以内に観測所がありません。予報は最寄りの観測所のもので、お住まいの場所を表さない場合があります。';

  @override
  String get useMyLocation => '現在地を使う';

  @override
  String get locationDenied => '位置情報の権限が拒否されました。場所を検索してください。';

  @override
  String get locationUnavailable => 'このデバイスでは位置情報を利用できません。';

  @override
  String get locationTimeout => '現在地を取得できませんでした。再試行するか、場所を検索してください。';

  @override
  String get yourLocation => '現在地';

  @override
  String get aboutPlacesTitle => '場所データ';

  @override
  String get aboutPlacesNote => '場所名は GeoNames に由来し、このデバイス上の検索にのみ使用されます。';

  @override
  String get aboutPrivacyTitle => 'プライバシー';

  @override
  String get aboutPrivacyNote => '場所検索と位置情報はこのデバイス内に留まり、地図タイルのみが地図提供元に要求されます。';
}
