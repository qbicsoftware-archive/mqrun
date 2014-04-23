import json
from copy import deepcopy
import collections
from xml.etree import ElementTree
from pathlib import PureWindowsPath

try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO


__all__ = ['xml_to_data', 'data_to_xml']


with open('./schema_title.json') as f:
    _schema = json.load(f)


def encode(value):
    if isinstance(value, bool):
        return str(value).lower()
    else:
        return str(value)


def decode(string, dtype):
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
    assert isinstance(d, collections.Mapping)
    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            r = rec_update(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


def data_to_xml(user_data, default_data, file_paths, output_dir, tmp_dir):
    extra_data = ExtraMQData(file_paths, output_dir, tmp_dir)

    root = ElementTree.Element('MaxQuantParams')
    tree = ElementTree.ElementTree(root)

    for klass, key in [(MSMSParams, 'msmsParams'),
                       (GlobalParams, 'globalParams'),
                       (RawFileParams, 'rawFiles')]:
        writer = klass(default_data)
        writer.update_data(user_data, extra_data)
        writer.add_to_xml(root)

    xml_file = BytesIO()
    tree.write(xml_file, 'utf-8')
    return xml_file.getvalue().decode()


def xml_to_data(xml_tree):
    data = {}

    global_params = GlobalParams()
    global_params.from_xml(xml_tree)
    raw_file_params = RawFileParams()
    raw_file_params.from_xml(xml_tree)
    msms_params = MSMSParams()
    msms_params.from_xml(xml_tree)

    data['globalParams'] = global_params.data
    data['rawFiles'] = raw_file_params.data
    data['MSMSParams'] = msms_params.data

    extra_data = raw_file_params.extra_data

    return data, extra_data


ExtraMQData = collections.namedtuple(
    'ExtraMQData',
    ['file_paths', 'output_dir', 'tmp_dir']
)


class MQParamSet(object):

    @property
    def data(self):
        return self._data

    @property
    def extra_data(self):
        return self._extra_data

    def __init__(self, schema):
        self._schema = schema
        self._data = None
        self._extra_data = ExtraMQData(None, None, None)

    def update_data(self, user_data=None, extra_data=None):
        if extra_data is not None:
            for i, dat in enumerate(extra_data):
                if dat is not None:
                    self._extra_data[i] = dat

        if user_data is not None:
            rec_update(self._data, user_data)

    def from_xml(self, xml_tree, ignore=[]):
        if not self._schema["type"] == "object":
            raise ValueError("type {} not supported"
                             .format(self._schema["type"]))

        base = xml_tree.find("MaxQuantParam")
        self._simple_read_from_xml(base, self._schema['properties'],
                                   ignore=ignore)

    def write_into_xml(self, xml_tree, ignore=[]):
        if not self._schema["type"] == "object":
            raise ValueError("type {} not supported"
                             .format(self._schema["type"]))

        base = xml_tree.find("MaxQuantParam")
        self._simple_write_into_xml(base, self.data,
                                    self._schema['properties'], ignore=ignore)

    def _simple_read_from_xml(self, base_element, schema, ignore=[]):
        ignore = set(ignore)

        data = {}
        for key in schema["properties"]:
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

        self.update_data(data)

    def _simple_write_into_xml(self, base_element, data, schema, ignore=[]):
        ignore = set(ignore)

        for key, value in data.items():
            if key in ignore or key not in schema:
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
                data_el.text = encode(value)


class RawFileParams(MQParamSet):

    def __init__(self):
        super().__init__(_schema['properties']['rawFiles'])

    def update_data(self, user_data=None, extra_data=None):
        if user_data is not None:
            data = []
            for user_item in user_data:
                default = deepcopy(self._data[0])
                rec_update(default, user_item)
                data.append(default)

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
                params_xml, params_schema['properties']
            )

        self.update_data(files)

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
            params_schema = self._schema['items']['properties']['params']
            self._simple_write_into_xml(
                param_group, file_data['params'], params_schema
            )
            param_groups.append(param_group)


class MSMSParams(MQParamSet):

    def __init__(self):
        super().__init__(_schema['properties']['MSMSParams'])

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

    def add_to_xml(self, xml_tree):
        ignore = {'#msmsParamsArray'}
        super().add_to_xml(xml_tree, ignore)

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

    def __init__(self):
        super().__init__(_schema['properties']['globalParams'])
