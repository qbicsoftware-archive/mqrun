import json
from copy import copy, deepcopy
import collections
from xml.etree import ElementTree
from pathlib import PureWindowsPath

try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO


with open('./schema_title.json') as f:
    _schema = json.load(f)


def encode(value):
    if isinstance(value, bool):
        return str(value).lower()
    else:
        return str(value)


def decode(string, dtype):
    if not string:
        if dtype == "string":
            return ""
        else:
            raise ValueError("invalid value {} for type {}".format(
                string, dtype))
    if dtype == "number":
        return float(string.strip())
    if dtype == "string":
        return string.strip()
    if dtype == "integer":
        return int(string.strip())
    if dtype == "boolean":
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
    assert isinstance(d, collections.Mapping)
    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            r = rec_update(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


def data_to_xml(user_data, default_data, file_paths, output_dir, tmp_dir):
    root = ElementTree.Element('MaxQuantParams')
    tree = ElementTree.ElementTree(root)

    for klass in [MSMSParams, GlobalParams]:
        writer = klass(default_data)
        writer.update_data(user_data)
        writer.add_to_xml(root)

    writer = RawFileParams(default_data, file_paths)
    writer.update_data(user_data)
    writer.add_to_xml(root)

    xml_file = BytesIO()
    tree.write(xml_file, 'utf-8')
    return xml_file.getvalue().decode()


def xml_to_data(xml_tree, default_data):
    data = {}

    global_params = GlobalParams(default_data)
    global_params.from_xml(xml_tree)
    raw_file_params = RawFileParams(default_data, None)
    raw_file_params.from_xml(xml_tree)
    msms_params = MSMSParams(default_data)
    msms_params.from_xml(xml_tree)

    data['globalParams'] = global_params._data
    data['rawFiles'] = raw_file_params._data
    data['MSMSParams'] = msms_params._data

    return data


class RawFileParams:

    def __init__(self, default_data, file_paths):
        self._file_paths = file_paths
        self._data = copy(default_data['rawFiles'])
        self._schema = _schema['properties']['rawFiles']

    def update_data(self, user_data):
        data = []
        for user_item in user_data['rawFiles']:
            default = deepcopy(self._data[0])
            rec_update(default, user_item)
            data.append(default)

        self._data = data

    def from_xml(self, xml_tree):
        root = xml_tree.getroot()

        files = []
        self._data = files

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

        for i, param_group in enumerate(param_group_inds):
            index = int(param_group.text.strip())
            params_xml = param_groups[index]
            files[i]['params'] = self._group_params_from_xml(params_xml)

    def _group_params_from_xml(self, elem):
        params = {}
        schema = self._schema['items']['properties']['params']['properties']

        for key in schema:
            if key in ['enzymes', 'variableModifications',
                       'enzymesFirstSearch']:
                items = []
                for string in elem.find(key):
                    items.append(string.text.strip())
                params[key] = items
            elif key in ['variableModificationsFirstSearch', 'labelMods']:
                items = []
                for string in elem.find(key):
                    items.append(string.text.strip().split(';'))
                params[key] = items
            elif key == 'additionalVariableModificationProteins':
                pass  # TODO
            elif key == 'additionalVariableModifications':
                pass  # TODO
            elif key == 'isobaricLabels':
                pass  # TODO
            else:
                params[key] = decode(elem.find(key).text, schema[key]["type"])

        return params

    def add_to_xml(self, xml_root):
        assert isinstance(self._data, list)

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
            experiment.text = encode(file_data['experiment'])
            experiments.append(experiment)

            file_path = ElementTree.Element('string')
            if file_data['name'] not in self._file_paths:
                file_path.text = encode(file_data['path'])
            else:
                file_path.text = encode(self._file_paths[file_data['name']])
            file_paths.append(file_path)

            fraction = ElementTree.Element('short')
            fraction.text = encode(file_data['fraction'])
            fractions.append(fraction)

            matching_ = ElementTree.Element('unsignedByte')
            matching_.text = encode(file_data['matching'])
            matching.append(matching_)

            param_group_ind = ElementTree.Element('int')
            param_group_ind.text = encode(i)
            param_group_inds.append(param_group_ind)

            param_group = ElementTree.Element('parameterGroup')
            self._add_group_params_to_xml(param_group, file_data['params'])
            param_groups.append(param_group)

    def _add_group_params_to_xml(self, base, params):
        assert isinstance(params, collections.Mapping)
        for key, value in params.items():
            if key in ['enzymes', 'variableModifications',
                       'enzymesFirstSearch']:
                assert isinstance(value, list)
                elem = ElementTree.Element(key)
                base.append(elem)
                for item in value:
                    assert isinstance(item, str)
                    string_el = ElementTree.Element('string')
                    string_el.text = encode(item)
                    elem.append(string_el)
            elif key in ['variableModificationsFirstSearch', 'labelMods']:
                assert isinstance(value, list)
                elem = ElementTree.Element(key)
                base.append(elem)
                for item in value:
                    assert isinstance(item, list)
                    string_el = ElementTree.Element('string')
                    string_el.text = encode(';'.join(item))
                    elem.append(string_el)
            elif key == 'additionalVariableModificationProteins':
                pass  # TODO
            elif key == 'additionalVariableModifications':
                pass  # TODO
            elif key == 'isobaricLabels':
                pass  # TODO
            else:
                elem = ElementTree.Element(key)
                elem.text = encode(value)
                base.append(elem)


class MSMSParams:

    def __init__(self, default_data):
        self._keys = _schema['properties']['MSMSParams']['properties'].keys()
        self._schema = _schema['properties']['MSMSParams']['properties']
        self._data = copy(default_data['MSMSParams'])

    def update_data(self, user_data):
        if 'MSMSParams' in user_data:
            rec_update(self._data, user_data['MSMSParams'])

    def from_xml(self, xml_tree):
        self._data = {}
        for key in self._schema:
            if key == 'msmsParamsArray':
                msms_data = []
                array_root = xml_tree.find(key)
                schema = self._schema['msmsParamsArray']['items']['properties']
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
            else:
                elem = xml_tree.find(key)
                try:
                    self._data[key] = decode(elem.text, self._schema[key]['type'])
                except ValueError:
                    raise ValueError("Could not decode element " + key)

    def add_to_xml(self, xml_root):
        for key, val in self._data.items():
            if key not in self._keys:
                raise ValueError('Invalid data item: ' + key)

            base = ElementTree.Element(key)
            xml_root.append(base)

            if key == 'msmsParamsArray':

                assert isinstance(val, list)
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
            else:
                base.text = encode(val)


class GlobalParams:

    def __init__(self, default_data):
        self._keys = _schema['properties']['globalParams']['properties'].keys()
        self._schema = _schema['properties']['globalParams']['properties']
        self._data = copy(default_data['globalParams'])

    def update_data(self, user_data):
        rec_update(self._data, user_data['globalParams'])

    def from_xml(self, xml_tree):
        self._data = {}
        root = xml_tree.getroot()
        for key, val in self._schema.items():

            if key in ['restrictMods', 'fixedModifications']:
                mods = []
                for string in root.find(key):
                    mods.append(string.text.strip())
                self._data[key] = mods

            else:
                elem = root.find(key)
                schema = self._schema[key]
                try:
                    self._data[key] = decode(elem.text, schema['type'])
                except ValueError:
                    raise ValueError(
                        "Could not parse key {}".format(key))

    def add_to_xml(self, xml_root):
        for key, val in self._data.items():
            base = ElementTree.Element(key)
            xml_root.append(base)

            if key == 'restrictMods':

                assert isinstance(val, list)
                for name in val:
                    string_el = ElementTree.Element('string')
                    string_el.text = name
                    base.append(string_el)

                #rpq = ElementTree.Element('restrictProteinQuantification')
                #rpq.text = encode(len(val) != 0)
                #xml_root.append(rpq)
            elif key == 'fixedModifications':
                assert isinstance(val, list)
                for name in val:
                    string_el = ElementTree.Element('string')
                    string_el.text = name
                    base.append(string_el)
            else:
                base.text = encode(val)
