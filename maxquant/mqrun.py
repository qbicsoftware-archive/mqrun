import os
import glob
import shutil
import subprocess

from multiprocessing import Pool, Process
from collections import namedtuple

CopyFromTo = namedtuple('CopyFromTo', ['copy_from', 'copy_to'])
XmlRawSize = namedtuple('XmlRawSize', ['xml', 'raw', 'size'])

from . tools import my_cp, setup_custom_logger, yaml_load

mylog = setup_custom_logger(__name__)
mylog.debug('Entering {0}'.format(__name__))

run_types = ['individual', 'combined', 'all']

def make_directory(yaml_data, dir_type=None, directory=None, filename=None):
    dir_types = ['output', 'process']
    if dir_type not in dir_types:
        raise NotImplementedError('This directory type has not been implemented.', dir_type, dir_types)

    if filename is not None:
        drive, tail = os.path.splitdrive(filename)
        dummy, fn = os.path.split(tail) 
        fn_base, fn_ext = os.path.splitext(fn)

    if directory is not None:
        drive, tail = os.path.splitdrive(directory)
        dummy, base_directory = os.path.split(tail) 
        
    if dir_type == 'output':
        drive = yaml_data['output_drive']
        directory_list = yaml_data['output_dir'] 
        
    elif dir_type == 'process':
        drive = yaml_data['process_drive']
        directory_list = [yaml_data['process_dir']]
        if directory is not None:
            directory_list.append(base_directory)
        
    if os.name == 'posix':
        o_drive = ''
    elif os.name == 'nt':
        o_drive = '{0}:\\'.format(drive)
        if not os.path.exists(o_drive):
            msg = 'output_drive specified in yaml_file does not exist'
            raise UserWarning(msg, (o_drive, yaml_data))

    s_dir = o_drive
    for item in directory_list:
        s_dir = os.path.join(s_dir, item)
        if not os.path.exists(s_dir):
            mylog.info('Making directory: {0}'.format(s_dir))
            os.mkdir(s_dir)

    if filename is not None:
        s_dir = os.path.join(s_dir, fn)
        
    return s_dir

def make_storage_name(raw_file_name_base, add_filename=False, storage_drive='M', storage_dir_list=['Orbi1']):
    
    date_info = raw_file_name_base.split('_')[0]
    year = date_info[:2]
    month = date_info[2:4]
    day = date_info[4:6]

    els = ['{0}:'.format(storage_drive)]
    for storage_dir in storage_dir_list:
        els.append(storage_dir)

    els += ['T{0}'.format(year), 'T{0}{1}'.format(year, month)]

    if int(year) < 12 or (int(year) == 12 and int(month) < 9):
        els += ['T{0}{1}{2}'.format(year, month, day)]
    
    if add_filename:
        els.append('{0}.raw'.format(raw_file_name_base))

    return os.path.join(*els)

def get_copy_data_from_YAML_files(filenames, run_type, label_combinations, single_experiment):

    if run_type not in run_types:
        raise UserWarning('run_type must be one of: {0}'.format(run_types), run_type)

    copy_data = []
    
    for yaml_file in filenames:
        with open(yaml_file, 'rb') as f:
            yaml_data = yaml_load(f)
            
        process_dir = make_directory(yaml_data, dir_type='process')
        output_dir = make_directory(yaml_data, dir_type='output')

        for label_comb in label_combinations:
            base_yaml_files = glob.glob(os.path.join(output_dir, '*{0}_mqpar.yaml'.format(label_comb)))        
            for base_yaml_file in base_yaml_files:
                if single_experiment:
                    if len(base_yaml_file.split(single_experiment)) == 1:
                        mylog.debug('Skipping YAML file: {0} with single experiment: {1}'.format(base_yaml_file,
                                                                                                 single_experiment))
                        continue
                
                run_type_elsA = base_yaml_file.split('all_{0}_mqpar.yaml'.format(label_comb))
                run_type_elsB = base_yaml_file.split('overall_{0}_mqpar.yaml'.format(label_comb))

                is_multiple = len(run_type_elsA) == 2 or len(run_type_elsB) == 2

                if is_multiple and run_type == 'individual':
                    skip = True
                elif not is_multiple and run_type in ['combined', 'all']:
                    skip = True
                else:
                    skip = False

                if skip:
                    mylog.info('Skipping YAML file: {0} with run type: {1}'.format(base_yaml_file, run_type))
                    continue

                byfb = base_yaml_file.split('.yaml')[0]
                xml_fn = '{0}.xml'.format(byfb)
                output_xml_fn = make_directory(yaml_data, dir_type='output', filename=xml_fn)
                process_xml_fn = make_directory(yaml_data, dir_type='process', directory=byfb, filename=xml_fn)

                with open(base_yaml_file, 'rb') as f:
                    yd = yaml_load(f)

                if type(yd['storage_dir']) != list:
                    storage_dir_list = []
                else:
                    storage_dir_list = yd['storage_dir']

                raw_pairs = []
                total_size = 0                    
                for key, rfnb in yd['raw-data-files'].items():
                    storage_raw_fn = make_storage_name(rfnb, add_filename=True,
                                                       storage_drive=yd['storage_drive'],
                                                       storage_dir_list=storage_dir_list)
                    total_size += os.path.getsize(storage_raw_fn)

                    process_raw_fn = make_directory(yd, dir_type='process', directory=byfb,
                                                    filename='{0}.raw'.format(rfnb))

                    mylog.debug('Copy data for: {0}   storage_fn: {1}  process_fn: {2}'.format(output_xml_fn,
                                                                                               storage_raw_fn,
                                                                                               process_raw_fn))
                    raw_pairs.append(CopyFromTo(storage_raw_fn, process_raw_fn))

                copy_data.append(XmlRawSize(CopyFromTo(output_xml_fn, process_xml_fn), raw_pairs, total_size))
                
    return copy_data
    

def test_filenames(filenames, filetype='YAML'):
        
    if not filenames:
        if filetype == 'YAML':
            msg = 'One or more YAML files must be specified to use this script.'
        elif filetype == 'XML':
            msg = 'Exactly two XML files must be specified to use this script.'
        else:
            msg = 'This filetype has not been implimented yet (not a user error)'
            raise NotImplementedError(msg, filetype)
        raise UserWarning(msg)

    for fn in filenames:
        if not os.path.exists(fn):
            msg = 'A filename specified does not exist: {0}'.format(fn)
            raise UserWarning(msg, (fn, filenames))

    if filetype == 'XML' and len(filenames) != 2:
        msg = 'Exactly two filenames must be specified'
        raise UserWarning(msg, (len(filenames), filenames))
        
def flatten_results(copy_data):

    results_dir, file_nameA = os.path.split(copy_data.xml.copy_from)

    process_dir, file_name = os.path.split(copy_data.xml.copy_to)
    xml_base = file_name.split('_mqpar.xml')[0]

    assert file_nameA == file_name
    
    cwd = os.getcwd()
    os.chdir(process_dir)
    
    os.system('del *.raw')
    os.system('del *.index')
    output_file = glob.glob('*output.txt')
    new_output_file = os.path.join(results_dir, xml_base, output_file[0])
    mylog.info('Moving MaxQuant stdout file to: {0}'.format(new_output_file))
    try:
        my_cp(output_file, new_output_file)
    except Exception as e:
        mylog.info('Move failed with: {0}'.format(e))
        pass
    
    os.chdir(os.path.join(process_dir, 'combined', 'txt'))
    output_files = glob.glob('*.txt') 
    for f in output_files:
        file_root = f.split('.txt')[0].replace(' ', '').replace('(', '_').replace(')', '_')
        new_file_name = os.path.join(results_dir, xml_base + '_' + file_root + '.csv')
        my_cp(f, new_file_name)

    os.chdir(process_dir)
    dir_list = os.listdir(process_dir)

    for item in dir_list:
        if not os.path.isfile(item):
            mylog.info('Removing directory: {0}'.format(item))
            shutil.rmtree(item)
    os.chdir(cwd)
    
def run_one_file(copy_data, mqpars, only_copy=False):
    
    xml_file_path = copy_data.xml.copy_to
    
    max_quant_cmd = r'C:\MaxQuant_{0}\bin\MaxQuantCmd.exe {1} {2}'.format(mqpars['maxquant_version'],
                                                                          xml_file_path,
                                                                          mqpars['mq_threads'])
    drive, tail = os.path.splitdrive(xml_file_path)
    head, fn = os.path.split(tail)
    fn_root, ext = os.path.splitext(fn)

    if not only_copy:
        mylog.info('Starting to run file: {0}'.format(xml_file_path))

        out_file_name = os.path.join(drive, head, '{0}_output.txt'.format(fn_root))
        mylog.info('Creating output file: {0}'.format(out_file_name))

        with open(out_file_name, 'w') as out_file:
            mylog.info('Executing : {0}'.format(max_quant_cmd))
            try:
                pr = subprocess.check_call(max_quant_cmd, shell=True, stdout=out_file, 
                                           stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                mylog.debug('Error in MaxQuant subprocess call: {0}'.format(e))
            
    flatten_results(copy_data)
    return True

def run_bunch(copy_data, mqpars, only_copy=False):

    results = []
    def collect_results(result):
        results.extend([result])
    
    p = Pool(processes=mqpars['threads'])

    for cpd in copy_data:
        if only_copy:
            mylog.info('Copying MaxQuant output (without running).')
            results.append(run_one_file(cpd, mqpars, only_copy=only_copy))
        else:
            mylog.info('Starting MaxQuant bunch with {0} raw files.'.format(len(cpd.raw)))
            mqpars['mq_threads'] = len(cpd.raw)
            p.apply_async(run_one_file, args = (cpd, mqpars), callback=collect_results)

    if not only_copy:
        p.close()
        p.join()
    
    return results
                    
def move_data_files(copy_data, max_size=None, only_copy=False):

    if os.name == 'nt':
        total_size = 0
        next_copy_data = []
        this_copy_data = []
        for cpd in copy_data:

            total_size += cpd.size
            if total_size < max_size:
                this_copy_data.append(cpd)
                if not os.path.exists(cpd.xml.copy_to):
                    if not only_copy:
                        my_cp(cpd.xml.copy_from, cpd.xml.copy_to)
                for fns in cpd.raw:
                    if not os.path.exists(fns.copy_to):
                        if not only_copy:
                            my_cp(fns.copy_from, fns.copy_to)
            else:
                next_copy_data.append(cpd)

        return next_copy_data, this_copy_data
    else:
        raise UserWarning('This function only operates on os.name="nt".', os.name)

    
def run_maxquant(copy_data, max_size, mqpars, only_copy=False):
    
    while True:
        copy_data, this_copy_data = move_data_files(copy_data, max_size=max_size, only_copy=only_copy)

        next_files_to_process = '\n'
        for cpd in copy_data:
            next_files_to_process += '    {0}\n'.format(cpd.xml.copy_from)
        if next_files_to_process.strip() != '':
            mylog.info('Will process these files later: {0}'.format(next_files_to_process))
        
        results = run_bunch(this_copy_data, mqpars, only_copy=only_copy)

        mylog.info('Batch run results: {0}'.format(results))
        
        if len(copy_data) == 0:
            break
        