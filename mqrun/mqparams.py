"""
==========================================
Convert parameters (:mod:`mqrun.mqparams`)
==========================================

.. currentmodule:: mqrun.mqparams

Convert between json or yaml and MaxQuant configuration files.

Contents
========

.. autosummary::
    :toctree: generated/

    xml_to_data
    data_to_xml
    mqrun


Parameters files
================

Example data::

    >>> import json
    >>> from pathlib import Path
    >>> from pprint import pprint

    >>> # TODO how about some sensible parameters ;-)
    >>> with open('paramfile.json') as f:
    >>>    param_file = f.read()

    >>> print(param_file)
    {
        "rawFiles": [
            {
                "name": "input1",
                "params": {
                    "defaults": "default",
                    "variableModifications": [
                        "Oxidation (M)",
                    ]
                }
            },
            {
                "name": "input2",
                "params": {
                    "defaults" :"default",
                }
            }
        "fastaFiles": {
            "fileNames": ["fasta1"],
            "firstSearch": ["fasta1"],
        }
        "globalParams": {
            "defaults": "default",
            "matchBetweenRuns": True
        }
    }

    >>> # load json data
    >>> params = json.load(param_file)

Each parameter file must contain the sections "rawFiles" and "fastaFiles".
"globalParams" and "MSMSParams" are optional.

The input files (raw and fasta) are only identified by a unique name. You must
specify the paths for each of the input files in a dictionary and pass that to
the relevant functions.

The "params" sections in "rawFiles" and the sections "globalParams" and
"MSMSParams" have the optional argument "defaults", that specifies default
values for the other parameters in that section.

# TODO: write some of those and document how to add more

``mqschema.json`` contains a json-schema for this file format along with
descriptions for a few of the parameters.

Example
-------

To convert above parameters to xml wee need a mapping to the file paths of
the input files. Let's say they are stored in the following locations::


    >>> paths = {
    >>>     "input1": Path("C://data/input1.raw")
    >>>     "input2": Path("C://data/input2.raw")
    >>>     "fasta1": Path("C://data/fasta1.fasta")
    >>> }

Convert to xml::

    >>> outdir = Path('C://output/')
    >>> tmpdir = Path('C://tmp')
    >>> xmltree = data_to_xml(params, paths, outdir, tmpdir)

We can now write that xml file to disk and run MaxQuantCmd on it::

    >>> xmltree.write(str(outdir / "params.xml"))

To convert it back to our json format we do::

    >>> params_, path_data = xml_to_data(xmltree)
    >>> path_data.paths == paths
    True
    >>> path_data.outdir == outdir
    True
    >>> path_data.tmpdir == tmpdir
    True

Since the xml file does not contain information about which default values
have been used, it specifies all values and differs from the original.
But converting it back to xml should yield the same result as before::

    >>> from sort_xml_tags import equal_sorted
    >>> xmltree_ = data_to_xml(params_, *path_data)
    >>> equal_sorted(xmltree_, xmltree)
    True

"""

import json
from copy import deepcopy
import collections
from xml.etree import ElementTree
from pathlib import PureWindowsPath, Path
import subprocess
import logging
import numbers

__all__ = ['xml_to_data', 'data_to_xml', 'mqrun']


datadir = Path(__file__).parent / "data"

with (datadir / 'mqschema.json').open() as f:
    _schema = json.load(f)


with (datadir / 'default_values.json').open() as f:
    _vals = json.load(f)
    _defaults = {}
    _defaults['default'] = {}
    _defaults.setdefault('globalParams', {})['default'] = _vals['globalParams']
    _defaults.setdefault('MSMSParams', {})['default'] = _vals['MSMSParams']
    _defaults.setdefault('rawFileParams', {})['default'] = (
        _vals['rawFiles'][0]['params']
    )
    _defaults.setdefault('topLevelParams', {})['default'] = (
        _vals['topLevelParams']
    )


def encode(value):
    """ Encode a value for use in xml """
    # Use capital E in scientific notation
    if isinstance(value, numbers.Number):
        return str(value).replace('e', 'E')
    elif isinstance(value, bool):
        return str(value).lower()
    else:
        return str(value)


def decode(string, dtype):
    """ Decode a value from an xml-file as dtype """
    if string is None:
        return None
    if dtype == "number":
        return float(string.strip())
    elif dtype == "string":
        return string.strip()
    elif dtype == "integer":
        return int(string.strip())
    elif dtype == "boolean":
        s = string.strip()
        if s == "true":
            return True
        elif s == "false":
            return False
        else:
            raise ValueError("not a bool: " + s)

    raise ValueError("Could not parse '{}' as type {}, type not known".format(
        string, dtype))


def rec_update(d, u):
    """ Recursivly update a nested dictionary.

    See https://stackoverflow.com/questions/3232943
    """
    assert isinstance(d, collections.Mapping)
    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            r = rec_update(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]


def data_to_xml(user_data, file_paths, fasta_paths,
                output_dir, tmp_dir=None, logger=None):
    """ Convert parameter set to MaxQuant xml.

    Parameters
    ----------
    user_data : dict
        The parameters for MaxQuant as described the module doc of mqparams.
    file_paths : dict
        Mapping from names in parameter set to actual file paths.
    fasta_paths : dict     # TODO merge with file_paths
        Mapping from names to file paths.
    output_dir : pathlib.Path
        Write the output files to this directory.
    tmp_dir : pathlib.Path, optional
        Base dir for temporary data, needs lots of space. Use system default
        if not specified.
    logger : logging.Logger, optional
        Logger for the conversion process. Use
        ``logging.getLogger('mqparams')`` if not specified

    Returns
    -------
    params_xml : xml.lxml.ElementTree.ElementTree
        Configuration file for use with ``MaxQuantCmd.exe``

    """
    if logger is None:
        logger = logging.getLogger('mqparams')

    if file_paths is None:
        file_paths = {}
    if fasta_paths is None:
        fasta_paths = {}
    extra_data = ExtraMQData(file_paths, fasta_paths, output_dir, tmp_dir)

    root = ElementTree.Element('MaxQuantParams')
    tree = ElementTree.ElementTree(root)

    for klass, key in [(MSMSParams, 'MSMSParams'),
                       (GlobalParams, 'globalParams'),
                       (RawFileParams, 'rawFiles'),
                       (OutputParams, None),
                       (FastaParams, 'fastaFiles'),
                       (TopLevelParams, 'topLevelParams')]:
        writer = klass(logger)
        writer.update_data(extra_data=extra_data)
        if key is not None:
            writer.update_data(user_data.get(key, None))
        writer.write_into_xml(tree)

    return tree


def xml_to_data(xml_tree, logger=None):
    """ Extract parameters and file-paths from MaxQuant configuration file

    Parameters
    ----------
    xml_tree : xml.etree.ElementTree.Element.Tree
        MaxQuant configuration file.
    logger : logging.Logger, optional
        Logger for the conversion process. Use
        ``logging.getLogger('mqparams')`` if not specified.

    Returns
    -------
    params : dict
        Parameters as described in module doc
    path_data : mqparams.ExtraMQData
        Path information from xml file

    extra_data has the following attributes:

    file_paths : dict
        Mapping from names for input files to paths
    fasta_paths : dict  # TODO merge with file_paths
        Same for fasta files
    output_dir : pathlib.Path
        Path to the output directory
    tmp_dir : pathlib.Path
        Path to temporary directory
    """
    if logger is None:
        logger = logging.getLogger('mqparams')
    data = {}
    extra = ExtraMQData(None, None, None, None)

    for klass, key in [(MSMSParams, 'MSMSParams'),
                       (GlobalParams, 'globalParams'),
                       (RawFileParams, 'rawFiles'),
                       (OutputParams, None),
                       (FastaParams, 'fastaFiles'),
                       (TopLevelParams, 'topLevelParams')]:
        reader = klass(logger)
        reader.from_xml(xml_tree)
        if key is not None:
            data[key] = reader.data
        reader.update_data(extra_data=extra)
        extra = reader.extra_data

    return data, extra


def mqrun(binpath, params, raw_files, fasta_files,
          outdir, tmpdir, logger=None):
    """  Run MaxQuant with specified parameters and paths. """
    if logger is None:
        logger = logging
    outdir = Path(outdir)
    logging.info("Writing parameter file")
    xml_path = outdir / "params.xml"
    with xml_path.open('wb') as f:
        xml = data_to_xml(params, raw_files, fasta_files,
                          outdir, tmpdir, logger)
        xml.write(f)
    logger.info("Run MaxQuant")
    mqcall = subprocess.Popen(
        [str(binpath), '-mqparams', str(xml_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    logger.info("MaxQuant running with pid " + str(mqcall.pid))
    mqcall.wait()


ExtraMQData = collections.namedtuple(
    'ExtraMQData',
    ['file_paths', 'fasta_paths', 'output_dir', 'tmp_dir']
)


class MQParamSet(object):

    @property
    def data(self):
        return self._data

    @property
    def extra_data(self):
        return self._extra_data

    def __init__(self, schema, defaults={}, logger=None):
        if logger is None:
            logger = logging
        self._logger = logger
        self._schema = schema
        self._data = None
        self._extra_data = ExtraMQData({}, {}, None, None)
        self._defaults = defaults

    def update_data(self, user_data=None, extra_data=None):
        if extra_data is not None:
            old = list(self._extra_data)
            for i, dat in enumerate(extra_data):
                if dat is not None and dat != {}:
                    old[i] = dat
            self._extra_data = ExtraMQData(*old)

        if user_data is not None and user_data != {}:
            if 'defaults' in user_data:
                self._data = deepcopy(self._defaults[user_data['defaults']])
            else:
                assert self._schema["type"] == 'object'
                self._data = {}
            rec_update(self._data, user_data)

    def from_xml(self, xml_tree, ignore=[]):
        if not self._schema["type"] == "object":
            raise ValueError("type {} not supported"
                             .format(self._schema["type"]))
        base = xml_tree.getroot()
        data = self._simple_read_from_xml(base, self._schema, ignore=ignore)
        self.update_data(data)

    def write_into_xml(self, xml_tree, ignore=[]):
        if not self._schema["type"] == "object":
            raise ValueError("type {} not supported"
                             .format(self._schema["type"]))

        base = xml_tree.getroot()
        self._simple_write_into_xml(base, self.data,
                                    self._schema, ignore=ignore)

    def _simple_read_from_xml(self, base_element, schema, ignore=[]):
        ignore = set(ignore)
        ignore.add('#defaults')
        if schema['type'] != 'object':
            raise ValueError("expected schema to contain an object")
        schema = schema['properties']

        data = {}
        for key in schema:
            if key == 'defaults':
                continue
            if schema[key]["id"] in ignore:
                continue

            el = base_element.find(key)
            type_ = schema[key]["type"]
            if type_ == "array":
                item_type = schema[key]["items"]["type"]
                if item_type == "string":
                    strings = [s.text.strip() for s in el]
                    data[key] = strings
                elif item_type == "array":
                    if not schema[key]["items"]["items"]["type"] == "string":
                        raise ValueError("can not decode element " + key)

                    strings = [s.text.split(';') for s in el]
                    data[key] = strings
                else:
                    raise ValueError("only list of list of string and " +
                                     "list of string are supported")
            else:
                data[key] = decode(el.text, type_)

        return data

    def _simple_write_into_xml(self, base_element, data, schema, ignore=[]):
        ignore = set(ignore)
        if schema['type'] != 'object':
            raise ValueError("expected schema to contain an object")
        schema = schema['properties']

        for key, value in data.items():
            if key == 'defaults':
                continue
            if key not in schema:
                raise ValueError("Unknown key: {}".format(key))
            if schema[key]['id'] in ignore:
                continue

            data_el = ElementTree.Element(key)
            base_element.append(data_el)

            if schema[key]["type"] == "array":
                assert isinstance(value, collections.Sequence)
                if schema[key]["items"]["type"] == "array":
                    for value_list in value:
                        assert isinstance(value_list, collections.Sequence)
                        str_el = ElementTree.Element("string")
                        str_el.text = ';'.join(encode(v) for v in value_list)
                        data_el.append(str_el)
                elif schema[key]["items"]["type"] == "string":
                    for val in value:
                        str_el = ElementTree.Element("string")
                        str_el.text = encode(val)
                        data_el.append(str_el)
                else:
                    raise ValueError("list of {} not supported"
                                     .format(schema[key]["items"]["type"]))
            else:
                if value is not None:
                    data_el.text = encode(value)


class RawFileParams(MQParamSet):

    def __init__(self, logger=None):
        super().__init__(
            _schema['properties']['rawFiles'],
            _defaults['rawFileParams'],
            logger,
        )

    def update_data(self, user_data=None, extra_data=None):
        if user_data is not None:
            data = []
            for user_item in user_data:
                if 'defaults' in user_item['params']:
                    default = deepcopy(
                        self._defaults[user_item['params']['defaults']]
                    )
                    rec_update(default, user_item['params'])
                    user_item['params'] = default
                data.append(user_item)

            self._data = data

        super().update_data(extra_data=extra_data)

    def from_xml(self, xml_tree):
        root = xml_tree.getroot()

        files = []

        experiments = root.find('experiments')
        file_paths = root.find('filePaths')
        fractions = root.find('fractions')
        matching = root.find('matching')
        param_group_inds = root.find('paramGroupIndices')
        param_groups = root.find('parameterGroups')

        for elems in zip(experiments, file_paths, fractions, matching):
            exp, path, frac, match = elems

            file = {}

            if exp.text and exp.text.strip():
                file['experiment'] = exp.text.strip()
            if path.text and path.text.strip():
                file['path'] = path.text.strip()
                file['name'] = PureWindowsPath(file['path']).stem
            if frac.text and frac.text.strip():
                file['fraction'] = int(frac.text.strip())
            if match.text and match.text.strip():
                file['matching'] = int(match.text.strip())

            files.append(file)

        params_schema = self._schema['items']['properties']['params']
        for i, param_group in enumerate(param_group_inds):
            index = int(param_group.text.strip())
            params_xml = param_groups[index]
            files[i]['params'] = self._simple_read_from_xml(
                params_xml, params_schema
            )

        self.update_data(files)

    def write_into_xml(self, xml_tree):
        assert isinstance(self._data, list)
        xml_root = xml_tree.getroot()

        experiments = ElementTree.Element('experiments')
        file_paths = ElementTree.Element('filePaths')
        fractions = ElementTree.Element('fractions')
        matching = ElementTree.Element('matching')
        param_group_inds = ElementTree.Element('paramGroupIndices')
        param_groups = ElementTree.Element('parameterGroups')

        xml_root.extend([experiments, file_paths, fractions, matching,
                         param_group_inds, param_groups])

        for i, file_data in enumerate(self._data):
            experiment = ElementTree.Element('string')
            if 'experiment' in file_data:
                experiment.text = encode(file_data['experiment'])
            experiments.append(experiment)

            file_path = ElementTree.Element('string')
            if file_data['name'] in self.extra_data.file_paths:
                file_path.text = encode(
                    self.extra_data.file_paths[file_data['name']]
                )
            else:
                file_path.text = encode(file_data['path'])
            file_paths.append(file_path)

            fraction = ElementTree.Element('short')
            if 'fraction' in file_data:
                fraction.text = encode(file_data['fraction'])
            fractions.append(fraction)

            matching_ = ElementTree.Element('unsignedByte')
            if 'matching' in file_data:
                matching_.text = encode(file_data['matching'])
            matching.append(matching_)

            param_group_ind = ElementTree.Element('int')
            param_group_ind.text = encode(i)
            param_group_inds.append(param_group_ind)

            param_group = ElementTree.Element('parameterGroup')
            params_schema = self._schema['items']['properties']['params']
            self._simple_write_into_xml(
                param_group, file_data['params'], params_schema
            )
            param_groups.append(param_group)


class MSMSParams(MQParamSet):

    def __init__(self, logger=None):
        super().__init__(
            _schema['properties']['MSMSParams'],
            _defaults['MSMSParams'],
            logger,
        )

    def from_xml(self, xml_tree):
        ignore = {'#msmsParamsArray'}
        super().from_xml(xml_tree, ignore)

        key = 'msmsParamsArray'
        array_schema = self._schema['properties']['msmsParamsArray']
        msms_data = []
        array_root = xml_tree.find(key)
        schema = array_schema['items']['properties']
        for param_set in array_root:
            data = {}
            for name in schema:
                if name in ['Tolerance', 'DeNovoTolerance']:
                    elem = param_set.find(name)
                    data[name] = {}
                    value_elem = elem.find("Value")
                    data[name]['value'] = decode(value_elem.text, "string")
                    unit_elem = elem.find("Unit")
                    data[name]['unit'] = decode(unit_elem.text, "string")
                else:
                    data[name] = param_set.attrib[name]
            msms_data.append(data)
        self._data[key] = msms_data

    def write_into_xml(self, xml_tree):
        ignore = {'#msmsParamsArray'}
        super().write_into_xml(xml_tree, ignore)

        key = 'msmsParamsArray'
        val = self._data[key]
        base = ElementTree.Element(key)
        xml_tree.getroot().append(base)

        assert isinstance(val, collections.Sequence)
        for param_set in val:
            param_set_el = ElementTree.Element('msmsParams')
            base.append(param_set_el)

            assert isinstance(param_set, collections.Mapping)
            for name, value in param_set.items():
                if name in ['Tolerance', 'DeNovoTolerance']:
                    tol = ElementTree.Element(name)
                    param_set_el.append(tol)

                    tol_val = ElementTree.Element('Value')
                    tol_val.text = encode(value['value'])
                    tol.append(tol_val)

                    tol_unit = ElementTree.Element('Unit')
                    tol_unit.text = encode(value['unit'])
                    tol.append(tol_unit)
                else:
                    param_set_el.attrib[name] = encode(value)


class GlobalParams(MQParamSet):

    def __init__(self, logger=None):
        super().__init__(
            _schema['properties']['globalParams'],
            _defaults['globalParams'],
            logger,
        )


class OutputParams(MQParamSet):

    def __init__(self, logger=None):
        super().__init__(
            _schema['properties']['outputOptions'],
            None,
            logger,
        )

    def from_xml(self, xml_tree, ignore=[]):
        assert ignore == []
        tmp_folder = decode(xml_tree.find('tempFolder').text, 'string')
        outdir = decode(xml_tree.find('fixedCombinedFolder').text, 'string')
        self.update_data(
            extra_data=ExtraMQData(None, None, outdir, tmp_folder)
        )

    def write_into_xml(self, xml_tree, ignore=[]):
        assert ignore == []
        data = self.extra_data
        root = xml_tree.getroot()
        tempFolder = ElementTree.Element('tempFolder')
        if data.tmp_dir is not None:
            tempFolder.text = encode(data.tmp_dir)
        root.append(tempFolder)

        outdir = ElementTree.Element('fixedCombinedFolder')
        if data.output_dir is not None:
            outdir.text = encode(data.output_dir)
        root.append(outdir)


class TopLevelParams(MQParamSet):

    def __init__(self, logger=None):
        super().__init__(
            _schema['properties']['topLevelParams'],
            _defaults['topLevelParams'],
            logger,
        )

    def from_xml(self, xml_tree, ignore=[]):
        assert ignore == []
        root = xml_tree.getroot()

        data = {}

        for key in self._schema['properties']:
            if key == 'defaults':
                continue

            data[key] = decode(
                root.attrib[key],
                self._schema['properties'][key]['type'],
            )

        self.update_data(user_data=data)

    def write_into_xml(self, xml_tree, ignore=[]):
        assert ignore == []
        root = xml_tree.getroot()

        for key in self._schema['properties']:
            if key == 'defaults':
                continue

            root.attrib[key] = encode(self.data[key])


class FastaParams(MQParamSet):

    def __init__(self, logger=None):
        super().__init__(
            _schema['properties']['fastaFiles'],
            None,
            logger,
        )

    def from_xml(self, xml_tree, ignore=[]):
        assert ignore == []
        root = xml_tree.getroot()

        data = {}

        fasta_files = {}

        for file in root.find('fastaFiles'):
            path = PureWindowsPath(file.text)
            fasta_files[path.stem] = str(path)

        data['fileNames'] = list(fasta_files.keys())

        first_search = []

        for file in root.find('fastaFilesFirstSearch'):
            path = PureWindowsPath(file.text)
            if fasta_files.get(path.stem, str(path)) != str(path):
                raise ValueError("File name for fasta file not unique")
            fasta_files[path.stem] = str(path)
            first_search.append(path.stem)

        data['firstSearch'] = first_search

        self.update_data(extra_data=ExtraMQData(None, fasta_files, None, None))
        self.update_data(user_data=data)

    def write_into_xml(self, xml_tree, ignore=[]):
        assert ignore == []
        root = xml_tree.getroot()

        file_paths = self.extra_data.fasta_paths

        base = ElementTree.Element('fastaFiles')
        root.append(base)

        for name in self.data['fileNames']:
            item = ElementTree.Element('string')
            base.append(item)
            item.text = file_paths[name]

        base = ElementTree.Element('fastaFilesFirstSearch')
        root.append(base)

        for name in self.data['firstSearch']:
            item = ElementTree.Element('string')
            base.append(item)
            item.text = file_paths[name]
