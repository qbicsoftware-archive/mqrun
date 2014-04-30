#!/usr/bin/env python
"""
Start a daemon, that listens for new directories. Each new directory that
satisfies some conditions will be interpreted as a request to run MaxQuant on
the files in that directory. The protocoll that is used to communicate failure
or success is described in `fscall.py`.

Load balancing
--------------
This program uses a semaphore to limit the number of instances that run
MaxQuant at the same time. If a task can not get access to MaxQuant after some
amount of time, its status will be set to FAILED. If a task runs for too long
it should be canceled, but this is not implemented yet (TODO).

Security
--------
mqdaemon will not follow symlinks that point outside the task directory.  Tasks
that use such symlinks as input files will fail.

All output and log files will be readable by *any user*, so if a request should
be private, their directory name should be impossible to guess (maybe use an
uuid4?). The directory containing the tasks should not have its execute bit
set for those users who are not allowed to access data. I am not really happy
about this solution, but for our particular setup I can not really see a
good alternative.

"""

from pathlib import Path
import threading
import logging
import argparse
import sys
import os
try:
    import yaml
except ImportError:
    yaml = None
import json

import fscall
import mqparams


MQBINPATH = Path() / "todo"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run MaxQuant on input/parameter files under listendir"
    )
    parser.add_argument('listendir', help="directory where tasks are dumped",
                        type=Path)
    parser.add_argument('-n', '--num-workers',
                        help="number of worker threads",
                        type=int, default=2)
    parser.add_argument('-s', '--timeout',
                        help="maximal time to wait until computation starts",
                        type=int, default=5)
    parser.add_argument('-b', '--read-interval',
                        help="seconds between scans for new tasks",
                        type=int, default=10)
    parser.add_argument('--mqpath', help="path tho MaxQuant binary",
                        type=Path, default=MQBINPATH)
    parser.add_argument('--task-re', help="regular expression for tasks",
                        default=None)
    parser.add_argument('--logfile',
                        help="global logfile for all MaxQuant runs",
                        default='./maxquant.log',
                        type=Path)

    args = parser.parse_args()
    if not args.mqpath.is_file():
        #print("No such file: {}".format(args.mqpath), file=sys.stderr)
        sys.exit(1)

    if not args.listendir.is_dir():
        #print("Not a directory: {}".format(args.listendir), file=sys.stderr)
        sys.exit(1)

    return args


def is_valid_file_below(log, file, basedir):
    """ Test if file is below basedir and can be accessed. """
    try:
        file = file.resolve()
    except OSError:
        log.warn("Invalid input file " + str(file), exc_info=True)
        return False
    if not file.parent == basedir:
        log.warn("Input file {} not in {}. Ignoring"
                 .format(str(basedir), str(file)))
        return False
    if not os.access(str(file), os.R_OK):
        log.warn("Can not read " + str(file))
        return False
    return True


def get_files(log, infiles):
    """ Seperate the infiles into raw, yaml/json and fasta files """
    raw_files = {}
    fasta_files = {}
    param_files = {}

    for file in infiles:
        if file.suffix.lower() == '.raw':
            raw_files[file.stem] = str(file)
        elif file.suffix.lower() == '.fasta':
            fasta_files[file.stem] = str(file)
        elif file.suffix.lower() in ['.yaml', '.json']:
            param_files[file.stem] = str(file)
        else:
            log.warn("Unknown input file: " + str(file))

    if len(param_files) > 1:
        log.error("Got more than one parameter file")
        raise ValueError("Too many parameter files")
    elif len(param_files) == 0:
        log.error("No parameter file")
        raise ValueError("No parameter file")
    param_file = Path(next(iter(param_files.values())))
    return param_file, raw_files, fasta_files


def parse_param_file(log, param_file):
    if param_file.suffix.lower() == '.yaml':
        log.debug("Found yaml parameter file: " + str(param_file))
        if yaml is None:
            log.error("No YAML support")
            raise ValueError("No YAML support")
        try:
            params = yaml.load(param_file.open().read())
        except yaml.YAMLError:
            log.error("Invalid YAML parameter file: " + str(param_file))
            raise
        except IOError:
            log.error("Could not read parameter file")
            raise
    elif param_file.suffix.lower() == '.json':
        log.debug("Found json parameter file: " + str(param_file))
        try:
            params = json.loads(param_file.open().read())
        except ValueError:
            log.error("Invalid json parameter file: " + str(param_file))
            raise
        except IOError:
            log.error("Could not read parameter file")
            raise
    else:
        assert False

    return params


def run_maxquant(log, infiles, outdir, tmpdir, workdir):
    """ Run MaxQuant on infiles and return paths of resulting files.

    Arguments
    ---------
    log : logging.Logger
        Logger for all events while running MaxQuant

    infiles : list of pathlib.Path
        Input files, including parameter file (json/yaml) for MaxQuant

    outdir : pathlib.Path
        Directory where to put output files of MaxQuant

    tmpdir : pathlib.Path
        Temporary directory for MaxQuant

    workdir : pathlib.Path
        Work directory for MaxQuant. All input files of MaxQuant will
        be copied here. This directory will be created by this function.

    Returns
    -------
    List of pathlib.Path for each output file of MaxQuant
    """

    log.debug("read input files")
    param_file, raw_files, fasta_files = get_files(log, infiles)

    log.debug("parse parameter file")
    params = parse_param_file(log, param_file)

    try:
        result = mqparams.mqrun(
            MQBINPATH, params, raw_files, fasta_files, outdir, tmpdir, log
        )
    except Exception:
        log.exception("Could not execute MaxQuant.")
        raise

    return result


def serve(listener, num_workers, timeout):
    """ Listen for new tasks in listendir and start worker thread. """
    sem = threading.BoundedSemaphore(num_workers)
    for task in listener:
        task_thread = threading.Thread(
            target=worker, name="worker-{}".format(task.uuid),
            args=(task, sem, timeout)
        )
        task.log.info("Create thread for new task " + task.uuid)
        task_thread.start()


def worker(task, sem, timeout=None):
    """ Run MaxQuant for given task. """
    try:
        with task.beat():
            task.log.debug("Checking input files")
            for file in task.infiles:
                if not is_valid_file_below(task.log, file, task._dir):
                    task.log.error("Invalid input file: %s, exiting", file)
                    task.error("Invalid input file {}".format(file))
                    return
            task.log.debug("Input files ok")
            task.log.info("Wait for resources")
            task.status('WAITING')
            if not sem.acquire(timeout=timeout):
                msg = "Timeout. No resources available."
                task.log.error(msg)
                task.error(msg)
                return

            try:
                task.status('WORKING')
                outfiles = run_maxquant(
                    task.log, task.infiles, task.outdir, task.outdir
                )
                task.success(outfiles)
            except Exception:
                task.log.exception("Error running MaxQuant")
                task.error("MaxQuant failed.")
            finally:
                sem.release()

    except Exception:
        logging.exception("Unknown error in worker thread")


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG,
        filename=str(args.logfile),
    )
    logging.info("starting daemon")
    logging.info("listendir is " + str(args.listendir))
    logging.info("timeout is " + str(args.timeout))
    logging.info("num_workers is " + str(args.num_workers))
    logging.info("path to maxquant is " + str(args.mqpath))
    listener = fscall.listen(
        args.listendir,
        task_re=args.task_re,
    )
    logging.info('start to listen in directory ' + str(args.listendir))
    serve(listener, args.num_workers, args.timeout)


if __name__ == '__main__':
    main()
