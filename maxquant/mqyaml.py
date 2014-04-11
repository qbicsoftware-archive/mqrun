import os
import glob
import shutil
import string
import itertools

from collections import defaultdict

from . mqrun import make_directory
from . mqxml import make_xml_string, build_xml_string
from . tools import pf, yaml_load, yaml_dump, setup_custom_logger
from . defaults import yaml_strings

mylog = setup_custom_logger(__name__)
mylog.debug('Entering {0}'.format(__name__))

def generate_default_xml(default_type):
    mylog.debug('Entering {0}'.format(generate_default_xml.__name__))
    
    if default_type not in yaml_strings.keys():
        raise UserWarning('This default xml type does not yet exist:', (default_type, yaml_strings.keys()))
    
    yaml_string = yaml_strings[default_type]
    default_yaml = yaml_load(yaml_string)
    mylog.debug('Data read from defaul YAML file: {0}'.format(pf(default_yaml)))

    default_yaml['raw-data-files'] = dict(A='FIRST_FILENAME')
    default_yaml['group-params'] = dict(A=default_type)
    default_yaml['process_drive'] = 'R'
    default_yaml['process_dir'] = 'PROCESS'
    
    return build_xml_string(default_yaml, is_storage=False)
                
def convert_YAML_files(filenames, label_combinations, single_experiment):
    for yaml_file in filenames:
        with open(yaml_file, 'rb') as f:
            yaml_data = yaml_load(f)
            
        output_dir = make_directory(yaml_data, dir_type='output')

        base_yaml_files = []
        for label_comb in label_combinations:
            base_yaml_files += glob.glob(os.path.join(output_dir, '*{0}_mqpar.yaml'.format(label_comb)))

        for base_yaml_file in base_yaml_files:
            if single_experiment:
                if len(base_yaml_file.split(single_experiment)) == 1:
                    mylog.debug('Skipping YAML file: {0}'.format(base_yaml_file))
                    continue
            
            xml_string = make_xml_string(base_yaml_file)

            drive, tail = os.path.splitdrive(base_yaml_file)
            dummy, fn = os.path.split(tail) 
            fn_base, fn_ext = os.path.splitext(fn)
            xml_fn = os.path.join(output_dir, '{0}.xml'.format(fn_base))

            with open(xml_fn, 'w') as f:
                mylog.info('Writing XML file: {0}'.format(xml_fn))
                #mylog.debug('   Contents of {0}: {1}'.format(xml_fn, xml_string))
                f.write(xml_string)
    
def build_YAML_file(files, output_file_name, experiment_type=None, labels=None, isotopic_labels=None, yaml_data=None):

    data_str = os.linesep
    group_str = os.linesep

    if len(files) > len(string.uppercase):
        msg = 'The number of files for each time or experiment is currently limited to: '
        raise NotImplementedError(msg, len(string.uppercase))

    file_dic = {}
    group_dic = {}
    for index, fn in enumerate(files):
        if labels:
            key = labels[index]
        else:
            key = string.uppercase[index]
        file_dic[key] = fn.split('.raw')[0]
        group_dic[key] = experiment_type

    new_yaml_data = {'raw-data-files':file_dic,
                     'group-params':group_dic,
                     'isotopic_labels':isotopic_labels}

    yaml_data.update(new_yaml_data)

    mylog.debug('Writing YAML data to {0}: {1}'.format(output_file_name, yaml_data))
    
    with open(output_file_name, 'wb') as f:
        mylog.info('Writing YAML file: {0}'.format(output_file_name))
        f.write(yaml_dump(yaml_data, default_flow_style=False))
    
def build_YAML_files(filenames, label_combination, run_type, single_experiment=None):
    base_exp_type = 'default'

    if single_experiment:
        mylog.info('Only running a single experiment: {0}'.format(single_experiment))

    labels_used = []
    for yaml_file in filenames:
        with open(yaml_file, 'rb') as f:
            yaml_data = yaml_load(f)

        output_dir = make_directory(yaml_data, dir_type='output')

        isotopic_labels = yaml_data['isotopic_labels']
        isotopic_keys = [item.keys()[0] for item in isotopic_labels]
        mylog.debug('Isotopic labels: {0}  keys: {1}'.format(isotopic_labels, isotopic_keys))
        if len(isotopic_labels) == 2:
            label_combinations = [''.join(sorted(isotopic_keys))]
        elif len(isotopic_labels) > 2:
            label_combinations = [''.join(sorted(labels)) for labels in list(itertools.combinations(isotopic_keys, 2))]
        elif len(isotopic_labels) == 1:
            assert len(isotopic_keys) == 1
            label_combinations = isotopic_keys
        else:
            raise UserWarning('isotopic_labels must be specified in the YAML file.', yaml_data['isotopic_labels'])
        mylog.debug('Label combinations: {0}'.format(pf(label_combinations)))

        for label_comb in label_combinations:
            if label_combination != 'all':
                if label_comb != label_combination:
                    mylog.info('Skipping label combination: {0}'.format(label_comb))
                    continue

            labels_used.append(label_comb)
            
            if len(label_comb) == 2:
                exp_type = '{0}_doubleSILAC'.format(base_exp_type)
            elif len(label_comb) == 1:
                exp_type = '{0}_labelfree'.format(base_exp_type)
            else:
                raise AssertionError('This label combination must be of length two or one: ', label_comb)
                
            it_labels = []
            for label in label_comb:
                for label_dic in isotopic_labels:
                    if label_dic.keys()[0] == label:
                        it_labels.append(label_dic)

            mylog.debug('labels identified: {0}'.format(it_labels))
            assert len(it_labels) in [1, 2]

            base_fn_label = '{0}_mqpar.yaml'.format(label_comb)
            
            if yaml_data.get('times'):
                all_file_info = defaultdict(list)
                for tp, file_list in yaml_data['times'].items():
                    ts = '_'.join([yaml_data['experiment'], str(tp), '{0}', base_fn_label])
                    fn_tmpl = os.path.join(output_dir, ts)

                    if single_experiment:
                        if len(ts.split(single_experiment)) == 1:
                            mylog.debug('Skipping time point: {0}'.format(tp))
                            continue

                    if len(file_list) > 1 and run_type in ['combined', 'all']:
                        build_YAML_file(file_list, fn_tmpl.format('all'), exp_type,
                                        isotopic_labels=it_labels, yaml_data=yaml_data)

                    if run_type in ['individual', 'all']:
                        for index, fn in enumerate(file_list):
                            build_YAML_file([fn], fn_tmpl.format(string.uppercase[index]), exp_type,
                                            isotopic_labels=it_labels, yaml_data=yaml_data)

                    all_file_info[str(tp)].append(fn)
                    
                all_files = []
                all_labels = []
                for key, fl in all_file_info.items():
                    all_files += fl
                    for f in fl:
                        all_labels.append(key)

                ts = '_'.join([yaml_data['experiment'], 'overall', base_fn_label])

                fn = os.path.join(output_dir, ts)

                if run_type in ['combined', 'all']:
                    if single_experiment:
                        if len(ts.split(single_experiment)) != 1:
                            continue
                    build_YAML_file(all_files, fn, exp_type, labels=all_labels,
                                    isotopic_labels=it_labels, yaml_data=yaml_data)

            elif yaml_data.get('experiments'):
                for exp_name, file_list in yaml_data['experiments'].items():
                    ts = '_'.join([yaml_data['experiment'], str(exp_name), '{0}', base_fn_label])
                    fn_tmpl = os.path.join(output_dir, ts)

                    if single_experiment:
                        if len(ts.split(single_experiment)) == 1:
                            mylog.info('Skipping experiment: {0}'.format(exp_name))
                            continue

                    if len(file_list) > 1 and run_type in ['combined', 'all']:
                        build_YAML_file(file_list, fn_tmpl.format('all'), exp_type,
                                        isotopic_labels=it_labels, yaml_data=yaml_data)

                    if run_type in ['individual', 'all']:
                        for index, fn in enumerate(file_list):
                            build_YAML_file([fn], fn_tmpl.format(string.uppercase[index]), exp_type,
                                            isotopic_labels=it_labels, yaml_data=yaml_data)

    return labels_used