'''
Module that provides tools used within the MaxQuant scripts.
'''
import os
import shutil
import pprint
import logging

import yaml
yaml_load = yaml.load
yaml_dump = yaml.dump

log_dir = '.log'
if not os.path.exists(log_dir):
    os.mkdir(log_dir)
    
def pf(item):
    return pprint.pformat(item)
    
def setup_custom_logger(name):

    class LevelFilter(logging.Filter):
        def __init__(self, level):
            self.level = level

        def filter(self, record):
            return record.levelno == self.level

    fh = logging.FileHandler(os.path.join(log_dir, '{0}.log'.format(name)))
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s'))

    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    sh.addFilter(LevelFilter(logging.INFO))
    
    logger = logging.getLogger(name)

    #logger.setLevel(logging.INFO)
    logger.setLevel(logging.DEBUG)

    logger.addHandler(fh)
    logger.addHandler(sh)

    return logger

mylog = setup_custom_logger(__name__)
mylog.debug('Entering {0}'.format(__name__))

def my_cp(from_file, to_loc):
    mylog.info('Copy from: {0}       to: {1}'.format(from_file, to_loc))
    shutil.copy(from_file, to_loc)


def change_fmt(item):
    '''
    Utility function to convert items to strings for YAML output.
    '''
    if type(item) == bool:
        return str(item).lower()
    elif type(item) == int or type(item) == float:
        return str(item)
    else:
        return item    
