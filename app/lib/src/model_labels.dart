/// Display labels for known model ids. Model names are identifiers, not UI
/// copy: they stay identical in every locale.
const Map<String, String> modelLabels = <String, String>{
  'ecmwf_ifs025': 'ECMWF IFS',
  'gfs_seamless': 'GFS',
};

String modelLabel(String id) => modelLabels[id] ?? id;
