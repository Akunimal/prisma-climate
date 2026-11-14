// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Chinese (`zh`).
class AppLocalizationsZh extends AppLocalizations {
  AppLocalizationsZh([String locale = 'zh']) : super(locale);

  @override
  String get appTitle => 'PRISMA · 按站点预报';

  @override
  String get appTagline => 'Open-Meteo 原始集合预报（GFS 与 ECMWF IFS），覆盖阿根廷 19 个站点。';

  @override
  String get tabStations => '观测站';

  @override
  String get tabForecast => '预报';

  @override
  String get tabAbout => '关于 / 状态';

  @override
  String get searchHint => '搜索站点';

  @override
  String get searchNoResults => '没有站点符合搜索条件。';

  @override
  String get stationsIntro => '选择一个站点查看其预报。';

  @override
  String get clearSearch => '清除';

  @override
  String get retry => '重试';

  @override
  String get loading => '正在加载数据…';

  @override
  String get labelIssue => '起报时间';

  @override
  String get labelExported => '导出时间';

  @override
  String get labelSmn => 'SMN 观测';

  @override
  String get labelClimateZone => '气候区';

  @override
  String get labelCoordinates => '坐标';

  @override
  String get argentinaTimeNote => '阿根廷时间（UTC−3）';

  @override
  String get variableT2mMax => '日最高温（t2m_max）';

  @override
  String get variableT2mMin => '日最低温（t2m_min）';

  @override
  String get variablePrecip => '降水（成员比例）';

  @override
  String get legendBand1090 => '10–90% 区间';

  @override
  String get legendBand2575 => '25–75% 区间';

  @override
  String get legendMedian => '中位数';

  @override
  String get legendModelsNeverPooled => '每个模型保留各自的成员和各自的分位数，绝不混合。';

  @override
  String get legendLeadAxis => '预报时效';

  @override
  String get noData => '无数据';

  @override
  String get missingMembersTitle => '无数据';

  @override
  String missingMembers(int members, int nominal) {
    return '无数据（$members/$nominal 个成员）';
  }

  @override
  String get observedTitle => 'SMN 观测 — 最近 30 天';

  @override
  String get observedNote => '按 SMN 原样提供的存档值；缺测保持为 null，绝不填补。';

  @override
  String get observedDate => '日期';

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
  String get precipNote => '可用成员中日累计降水达到或超过阈值的比例。';

  @override
  String get day => '天';

  @override
  String get date => '日期';

  @override
  String get model => '模型';

  @override
  String get rawBanner => '原始集合预报：未做偏差订正，也未校准。在 15 个起报日期的门槛之前不发布任何检验指标。';

  @override
  String get attributionTitle => '数据与署名';

  @override
  String get attributionObserved =>
      '观测序列：Servicio Meteorológico Nacional，按原样存档；缺测保持为 null，绝不填补。';

  @override
  String get attributionNote => '署名行按其许可要求逐字复制，仅翻译周围的说明文字。';

  @override
  String get aboutTitle => '关于 / 状态';

  @override
  String get aboutWhatTitle => '本应用展示什么';

  @override
  String get aboutWhat =>
      'PRISMA 为阿根廷 19 个站点发布两个集合（ECMWF IFS 与 GFS）的原始概率预报，最远 15 天，另加 SMN 最近 30 天观测的日最高、最低气温。本应用只读取发布在 GitHub Pages 上的静态文件：没有服务器，也没有 API。';

  @override
  String get aboutNoSkillTitle => '无技巧评分';

  @override
  String get aboutNoSkill =>
      '本应用不显示 CRPS、CRPSS、Brier 分数、可靠性、覆盖率或排行榜。在 15 个起报日期的门槛之前不发布这些数字。';

  @override
  String get aboutStatusTitle => '数据状态';

  @override
  String get aboutSourcesTitle => '来源与许可';

  @override
  String get aboutDataset => '数据集';

  @override
  String get aboutSmnSnapshot => 'SMN 快照（regtemp）';

  @override
  String get aboutRegion => '区域';

  @override
  String get aboutSchema => '模式';

  @override
  String get statusForecasts => '原始集合成员：未做偏差订正、未校准，除来源质量标记外未做质量控制。';

  @override
  String get statusVerification =>
      '在 docs/EVALUATION_PROTOCOL.md 的 15 个起报日期门槛之前，不发布任何检验结果（CRPS、CRPSS、Brier、可靠性、覆盖率、排行榜）。';

  @override
  String get statusObservations =>
      'SMN regtemp 快照按原样存档；缺测保持为 null，绝不填补。适用 2026-11-14 的产品优先级规则（regtemp 为主）。';

  @override
  String get aboutMachineTranslations => '英文以外的翻译由机器生成，欢迎纠错与改进。';

  @override
  String get languageLabel => '语言';

  @override
  String leadDay(int lead) {
    return '+$lead d';
  }

  @override
  String errorTitle(String document) {
    return '无法读取 $document';
  }

  @override
  String schemaUnsupported(String version) {
    return '本应用不支持架构版本“$version”（预期 1.0）。请更新应用或导出文件。';
  }

  @override
  String parseError(String document, String detail) {
    return '文档 $document 不是预期的格式：$detail';
  }

  @override
  String networkError(String document, String detail) {
    return '无法下载 $document：$detail';
  }

  @override
  String httpError(int status, String document) {
    return '数据源对 $document 返回了 HTTP $status。';
  }

  @override
  String invalidJson(String document, String detail) {
    return '$document 中的 JSON 无效：$detail';
  }

  @override
  String get modelsNonText => '“models”字段包含非文本值。';

  @override
  String fieldNotObject(String field) {
    return '字段“$field”不是 JSON 对象。';
  }

  @override
  String fieldNotArray(String field) {
    return '字段“$field”不是 JSON 数组。';
  }

  @override
  String missingTextField(String field) {
    return '缺少文本字段“$field”或其不是字符串。';
  }

  @override
  String missingIntegerField(String field) {
    return '缺少整数“$field”或其不是数字。';
  }

  @override
  String notNumericField(String field) {
    return '字段“$field”不是数值。';
  }

  @override
  String missingSchemaVersion(String document) {
    return '$document 中缺少 schema_version 字段。';
  }

  @override
  String stationCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count 个站点',
    );
    return '$_temp0';
  }

  @override
  String get stationsViewList => '列表';

  @override
  String get stationsViewMap => '地图';

  @override
  String get stationsViewForecast => '查看预报';

  @override
  String get mapLegend => '图例';

  @override
  String get mapReportProblem => '报告地图问题';

  @override
  String get mapTilesFailed => '无法加载地图瓦片。在中性背景上显示站点。';

  @override
  String get aboutMapTilesTitle => '地图瓦片';

  @override
  String get aboutMapTilesNote => '地图直接从 OpenStreetMap 服务器加载瓦片。';
}
