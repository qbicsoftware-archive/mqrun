import json
from copy import copy, deepcopy
import collections
from xml.etree import ElementTree

try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO


with open('./params_schema.json') as f:
    _schema = json.load(f)


def encode(value):
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return str(value).lower()
    else:
        return str(value)


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
            if key in ['enzymes', 'labelMods', 'variableModifications']:
                assert isinstance(value, list)
                elem = ElementTree.Element(key)
                base.append(elem)
                for item in value:
                    string_el = ElementTree.Element('string')
                    string_el.text = encode(item)
                    elem.append(string_el)
            elif key == 'variableModificationsFirstSearch':
                pass  # TODO
            else:
                elem = ElementTree.Element(key)
                elem.text = encode(value)
                base.append(elem)


class MSMSParams:

    def __init__(self, default_data):
        self._keys = _schema['properties']['MSMSParams']['properties'].keys()
        self._data = copy(default_data['MSMSParams'])

    def update_data(self, user_data):
        if 'MSMSParams' in user_data:
            rec_update(self._data, user_data['MSMSParams'])

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
        self._data = copy(default_data['globalParams'])

    def update_data(self, user_data):
        rec_update(self._data, user_data['globalParams'])

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

                rpq = ElementTree.Element('restrictProteinQuantification')
                rpq.text = encode(len(val) != 0)
                xml_root.append(rpq)
            elif key == 'fixedModifications':
                assert isinstance(val, list)
                for name in val:
                    string_el = ElementTree.Element('string')
                    string_el.text = name
                    base.append(string_el)
            else:
                base.text = encode(val)
