'''
Provides make_xml_string and build_xml_string which creates a MaxQuant XML input file from YAML data.
'''
import os
import sys

from xml.dom import minidom
from xml.etree import ElementTree as et
from xml.etree.ElementTree import tostring as et_tostring

from . mqrun import make_directory
from . tools import pf, change_fmt, yaml_load, setup_custom_logger
from . defaults import yaml_strings

from pprint import pformat
import yaml

try:
    from io import StringIO
except ImportError:
    from StringIO import StringIO


mylog = setup_custom_logger(__name__)
mylog.debug('Entering {0}'.format(__name__))

def _prettify(elem):
    """Return a pretty-printed XML string for the Element.
    """
    rough_string = et_tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding='utf-8')

def _add_parameter_group(cc, group_dic):
    se = et.SubElement

    #not_used = ['variableModificationsFirstSearch']
    #for v in not_used:
    #    ccc = se(cc, v)

    tlp_keys = ['maxCharge', 'lcmsRunType', 'msInstrument', 'groupIndex', 'maxLabeledAa',
                'maxNmods', 'maxMissedCleavages', 'multiplicity', 'protease', 'proteaseFirstSearch',
                'useProteaseFirstSearch', 'useVariableModificationsFirstSearch',
    ]

    for k in tlp_keys:
        v = group_dic['top-level-parameters'][k]
        ccc = se(cc, k)
        ccc.text = change_fmt(v)

    for k in ['variableModifications', 'isobaricLabels', 'variableModificationsFirstSearch']:
        v = group_dic[k]
        ccc = se(cc, k)
        for vv in v:
            cccc = se(ccc, 'string')
            cccc.text = vv

    tlp_keys = ['hasAdditionalVariableModifications']
    for k in tlp_keys:
        v = group_dic['top-level-parameters'][k]
        ccc = se(cc, k)
        ccc.text = change_fmt(v)

    not_used_array = ['additionalVariableModifications', 'additionalVariableModificationProteins']
    for v in not_used_array:
        ccc = se(cc, v)
        cccc = se(ccc, 'ArrayOfString')

    tlp_keys = ['doMassFiltering', 'firstSearchTol', 'mainSearchTol']
    for k in tlp_keys:
        v = group_dic['top-level-parameters'][k]
        ccc = se(cc, k)
        ccc.text = change_fmt(v)

    ccc = se(cc, 'labels')
    ll = group_dic['labels']
    for v in ll:
        cccc = se(ccc, 'string')
        if v:
            cccc.text = v

def make_xml_string(outdir, mqparams, raw_file_paths):
    '''
    Reads a YAML file and creates a MaxQuant XML file.

    Parameters
    ----------

    raw_file_paths:
            Full paths of input files, specified in mqparams

    mqparams:
            Dict of parameters for MaxQuant

    Returns
    -------
    mq_xml_string: str
                   An XML string that can be used as input to MaxQuant.
    '''
    mylog.debug('Data read from user YAML file: ' + pformat(mqparams))

    # Base experiment type is the same for all files -- we take the first one.
    first_key = list(mqparams['group_params'].keys())[0]  # TODO Hack
    exp_type = mqparams['group_params'][first_key]
    mylog.debug("user_data['group_params'][first_key]  " +
                "first_key:{0}  exp_type:{1}".format(first_key, exp_type))

    # check input files vs raw_paths
    files = {}
    full_paths = {path.stem: path for path in raw_file_paths}
    if len(full_paths) < len(raw_file_paths):
        mylog.error("base name of input files are not unique")

    for key, file_name in mqparams['raw_data_files'].items():
        try:
            files[key] = str(full_paths[file_name])
        except KeyError as e:
            mylog.critical("could not find raw input file: " + str(e))
            sys.exit(1)

    mqparams['raw_data_files'] = files
    print(files)

    yaml_string_tmpl = yaml_strings[exp_type]
    label_elements = []
    for label_dic in mqparams['isotopic_labels']:
        for label_key, label_list in label_dic.items():
            if label_list:
                label_elements.append('; '.join(label_list))
            else:
                label_elements.append('false')

    mylog.debug('Label elements: {0}'.format(label_elements))
    default_data = yaml.load(
        StringIO(yaml_string_tmpl.format(*label_elements))
    )

    mylog.debug(
        'Data read from defaul YAML file: {0}'.format(
            pformat(default_data)
        )
    )

    # TODO recursive update (https://stackoverflow.com/questions/3232943)
    default_data.update(mqparams)
    params = default_data

    mylog.debug(
        'Parameters for maxquant: {0}'.format(
            pformat(params)
        )
    )

    mylog.debug("start building xml file from yaml data")
    xml_str = build_xml_string(params, outdir)  # TODO error handling
    mylog.debug("building xml file done")
    return xml_str


def _set_tlp_keys(element, root, keys, yaml_data):
    for k in keys:
        v = yaml_data['top-level-parameters'][k]
        element = et.SubElement(root, k)
        out = change_fmt(v)
        if k == 'tempFolder' and out == 'false':
            continue
        element.text = out

def build_xml_string(yaml_data, output_directory):
    se = et.SubElement
    root = et.Element('MaxQuantParams')

    root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    root.set('xmlns:xsd', 'http://www.w3.org/2001/XMLSchema')
    root.set('runOnCluster', 'false')
    root.set('processFolder', str(output_directory))

    c = se(root, 'rawFileInfo')
    cc = se(c, 'filePaths')
    dd = se(c, 'fileNames')
    ee = se(c, 'paramGroups')
    ff = se(c, 'Fractions')
    gg = se(c, 'Values')
    ggg = se(gg, 'column')
    ggg.set('Name', 'Experiment')
    gggg = se(ggg, 'Items')

    for key, path in yaml_data['raw_data_files'].items():
        file_name = os.path.basename(path).split('.')[0]
        ccc = se(cc, 'string')
        ccc.text = path

        ddd = se(dd, 'string')
        ddd.text = file_name

        eee = se(ee, 'int')
        eee.text = '1'

        ggggg = se(gggg, 'Item')
        ggggga = se(ggggg, 'Key')
        ggggga.set('xsi:type', 'xsd:string')
        ggggga.text = file_name
        gggggb = se(ggggg, 'Value')
        gggggb.set('xsi:type', 'xsd:string')
        gggggb.text = key

    c = se(root, 'experimentalDesignFilename')
    c.text = ''

    # top-level-parameters set from YAML data:
    tlp_keys = ['slicePeaks', 'tempFolder', 'ncores', 'ionCountIntensities',
                'maxFeatureDetectionCores',
                'verboseColumnHeaders',
                'minTime',
                'maxTime',
                'calcPeakProperties',
                'useOriginalPrecursorMz']

    _set_tlp_keys(c, root, tlp_keys, yaml_data)

    # top-level-strings set from YAML data:
    for k, v in yaml_data['top-level-strings'].items():
        c = se(root, k)
        cc = se(c, 'string')
        cc.text = v

    tlp_keys = ['multiModificationSearch']
    for k in tlp_keys:
        v = yaml_data['top-level-parameters'][k]
        c = se(root, k)
        out = change_fmt(v)
        c.text = out

    c = se(root, 'fastaFiles')
    for fn in yaml_data['fasta-files']:
        cc = se(c, 'string')
        cc.text = 'D:\\FASTA\\{0}'.format(fn)

    elements_not_used = ['fastaFilesFirstSearch', 'fixedSearchFolder']
    for e in elements_not_used:
        c = se(root, e)

    tlp_keys = ['advancedRatios', 'rtShift', 'fastLfq', 'randomize', 'specialAas',
                'includeContamiants', 'equalIl', 'topxWindow', 'maxPeptideMass',
                'reporterPif', 'reporterFraction', 'reporterBasePeakRatio', 'scoreThreshold',
                'filterAacounts', 'secondPeptide', 'matchBetweenRuns', 'matchBetweenRunsFdr',
                'reQuantify', 'dependentPeptides', 'dependentPeptideFdr', 'dependentPeptideMassBin',
                'labelFree', 'lfqMinEdgesPerNode', 'lfqAvEdgesPerNode', 'hybridQuantification',
                'msmsConnection', 'ibaq', 'msmsRecalibration', 'ibaqLogFit', 'razorProteinFdr',
                'calcSequenceTags', 'deNovoVarMods', 'massDifferenceSearch', 'minPepLen',
                'peptideFdr', 'peptidePep', 'proteinFdr', 'siteFdr',
                'minPeptideLengthForUnspecificSearch','maxPeptideLengthForUnspecificSearch',
                'useNormRatiosForOccupancy', 'minPeptides', 'minRazorPeptides', 'minUniquePeptides',
                'useCounterparts', 'minRatioCount', 'lfqMinRatioCount', 'restrictProteinQuantification',
            ]
    _set_tlp_keys(c, root, tlp_keys, yaml_data)

    c = se(root, 'restrictMods')
    for rm in yaml_data['restrict-mods']:
        cc = se(c, 'string')
        cc.text = rm

    tlp_keys = ['matchingTimeWindow', 'numberOfCandidatesMultiplexedMsms','numberOfCandidatesMsms',
                'separateAasForSiteFdr']
    _set_tlp_keys(c, root, tlp_keys, yaml_data)

    elements_not_used = ['massDifferenceMods']
    for e in elements_not_used:
        c = se(root, e)


    aif_keys = ['aifSilWeight', 'aifIsoWeight', 'aifTopx', 'aifCorrelation', 'aifCorrelationFirstPass',
                'aifMinMass', 'aifMsmsTol', 'aifSecondPass', 'aifIterative', 'aifThresholdFdr',
            ]

    c = se(root, 'aifParams')
    for k, v in yaml_data['aif-parameters'].items():
        out = change_fmt(v)
        c.set(k, out)

    c = se(root, 'groups')
    cc = se(c, 'ParameterGroups')
    _add_parameter_group(cc, yaml_data['default-group'])


    elements_not_used = ['experimentalDesignFilename', 'tempFolder']
    c = se(root, 'qcSettings')
    for fn in yaml_data['raw_data_files'].values():
        cc = se(c, 'qcSetting')
        cc.set('xsi:nil', 'true')


    c = se(root, 'msmsParams')
    fsk_keys = ['FTMS', 'ITMS', 'TOF', 'Unknown']
    for fsk in fsk_keys:
        v_dic = yaml_data['msms-parameters']['fragment-spectrum-settings'][fsk]
        cc = se(c, 'FragmentSpectrumSettings')
        cc.set('Name', fsk)

        #Add parameters from the fragment-spectrum-settings dic.
        keys_used = []
        for ddk, ddv in v_dic.items():
            if ddk == 'Tolerance':
                ccc = se(cc, 'Tolerance')
                for tk, tv in v_dic['Tolerance'].items():
                    cccc = se(ccc, tk)
                    cccc.text = change_fmt(tv)
                continue
            keys_used.append(ddk)
            cc.set(ddk, change_fmt(ddv))

        #Add parameters from default if not specified in the fragment-spectrum-settings dic in the YAML file.
        for dk, dv in yaml_data['msms-parameters']['default'].items():
            if dk in keys_used:
                continue
            cc.set(dk, change_fmt(dv))

    tlp_keys = ['keepLowScoresMode', 'msmsCentroidMode', 'quantMode', 'siteQuantMode']
    _set_tlp_keys(c, root, tlp_keys, yaml_data)

    c = se(root, 'groupParams')
    for fnk, fn in yaml_data['raw_data_files'].items():
        cc = se(c, 'groupParam')
        _add_parameter_group(cc, yaml_data['default-group'])

    return _prettify(root)
