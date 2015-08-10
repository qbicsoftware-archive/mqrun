#!/usr/bin/env python
"""
MaxQuant Server.

Start a daemon that listens for new directories. Each new directory that
satisfies some conditions will be interpreted as a request to run MaxQuant on
the files in that directory. The protocoll that is used to communicate failure
or success is described in `fscall.py`.

Load balancing
--------------
This program uses a semaphore to limit the number of instances that run
MaxQuant at the same time. If a task can not get access to MaxQuant after some
amount of time, its status will be set to FAILED. If a task runs for too long
it is canceled.

Security
--------
All output and log files will probabley be readable by any user who has
permissions to use this service, so if you need private requests, use a
dedicated server process for each user.

"""
from __future__ import print_function

from pathlib import Path
import threading
import logging
import logging.handlers
import argparse
import sys
import subprocess
import tempfile
import os
import time
try:
    import yaml
except ImportError:
    yaml = None
import json

from . import fscall, mqparams


MQBINPATH = Path() / "todo"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run MaxQuant on input/parameter files under listendir"
    )
    parser.add_argument('listendir', help="directory where tasks are dumped",
                        type=Path)
    parser.add_argument('outdir', help='output directory', type=Path)
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
    parser.add_argument('--tmpdir', help='temporary directory for maxquant')
    parser.add_argument('--task-re', help="regular expression for tasks",
                        default=None)
    parser.add_argument('--maxtasks', help='maximum number of tasks to start',
                        default=None, type=int)
    parser.add_argument('--logfile',
                        help="global logfile for all MaxQuant runs",
                        default='maxquant.log',
                        type=Path)
    parser.add_argument('--logging-ip', help='Send logging to this ip via TCP')
    parser.add_argument('--logging-port', help='Port to use for logging-ip',
                        default=logging.handlers.DEFAULT_TCP_LOGGING_PORT,
                        type=int)

    args = parser.parse_args()

    try:
        args.mqpath = args.mqpath
    except (OSError, RuntimeError):
        print("Invalid mqpath: " + str(args.mqpath))
        sys.exit(1)
    if not args.mqpath.is_file():
        print("Not a file: {}".format(args.mqpath), file=sys.stderr)
        sys.exit(1)

    #try:
    #    args.listendir = args.listendir.resolve()
    #except (OSError, RuntimeError):
    #    print("Invalid listendir: " + str(args.listendir))
    #    sys.exit(1)
    if not args.listendir.is_dir():
        print("Not a directory: {}".format(args.listendir), file=sys.stderr)
        sys.exit(1)

    return args


def bucket_files(log, infiles):
    """ Seperate infiles into data- and parameter files"""
    datafiles = {}
    param_files = {}

    for file in infiles:
        if file.suffix.lower() in ['.raw', '.fasta']:
            if file.stem in datafiles:
                log.error("file name not unique: " + file.stem)
                raise ValueError("File name not unique")
            datafiles[file.stem] = str(file)
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
    return param_file, datafiles


def parse_param_file(log, param_file):
    """ Parse param_file as yaml or json file. """
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


def validate_params(log, params, datafiles):
    #raw_names = [raw['name'] for raw in group['files']
    #             for group in params['rawFiles']]
    #if len(set(raw_names)) != len(raw_names):
    #    raise ValueError(
    #        "Invalid parameter file. Names of raw files not unique."
    #    )
    pass


class MQJob(threading.Thread):
    """ Control a MaxQuant task.

    Execute MaxQuant in two stages:

    - Check input files (checksums) and read and validate parameter file.
      This should be done quickly, to make sure that errors get reported
      as soon as possible. ``prepare_sem`` protects this step.

    - Create MaxQuant xml file and execute MaxQuantCmd. ``mq_sem`` protects
      this step.

    TODO
    ----
    - Move creation of xml file to step 1
    - Copy data files to a temporary directory before at the beginning of step 1

    Arguments
    ---------
    task : fscall.Task
        The task that should be executed
    prepare_sem : threading.Semaphore
        A semaphore that protects checksums and parameter file generation.
        Theses should be executed as soon as possible to make errors visible.
    mq_sem : threading.Semaphore
        A spmaphore that protects the MaxQuant computation.
    sem_timeout : int, seconds
        The max time to wait for resources.
    mq_timeout : int, seconds
        The maximum running time for MaxQuant.
    tmpdir : str
        Base directory for all temporary directories used by MaxQuant.
    """
    def __init__(self, mqpath, task, prepare_sem, mq_sem, sem_timeout,
                 mq_timeout, tmpdir=None, **kwargs):
        super().__init__(**kwargs)
        self.task = task
        self.prepare_sem = prepare_sem
        self.mq_sem = mq_sem
        self.sem_timeout = sem_timeout
        self.mq_timeout = mq_timeout
        self.mq_timeout = float('inf')
        self.mqpath = mqpath
        self.tmpdir = tmpdir

    def _process_params(self):
        param_file, datafiles = bucket_files(self.task.log, self.task.infiles)
        params = parse_param_file(self.task.log, param_file)
        validate_params(self.task.log, params, datafiles)

        return params, datafiles

    def _run_maxquant(self, params, datafiles):
        with tempfile.TemporaryDirectory(dir=self.tmpdir) as tmpdir:
            log = self.task.log
            log.info('Executing MaxQuant with tempdir %s and outdir %s' % (
                str(tmpdir), str(self.task.outdir)))

            start = time.time()

            # MaxQuant writes status to combined/proc
            known_status_files = set()
            proc_dir = os.path.join(str(self.task.outdir), 'combined', 'proc')

            mqcall = mqparams.mqrun(
                self.mqpath,
                params,
                datafiles,
                self.task.outdir,
                tmpdir,
                self.task.log,
            )

            log.info("MaxQuant running with pid " + str(mqcall.pid))
            while True:
                try:
                    outs, errs = mqcall.communicate(timeout=5)
                    break
                except subprocess.TimeoutExpired:
                    if (self.mq_timeout is not None and
                            time.time() - start > self.mq_timeout):
                        log.error("MaxQuant timed out. Timeout was {}s"
                                  .format(self.mq_timeout))
                        mqcall.kill()
                        outs, errs = mqcall.communicate()
                        log.info("MaxQuant stdout: " + outs.decode())
                        log.info("MaxQuant stderr: " + errs.decode())
                        raise RuntimeError("MaxQuant timeout")
                    else:
                        try:
                            status_files = set(os.listdir(proc_dir))
                            new_status_files = known_status_files - status_files
                            for file in new_status_files:
                                log.info('New status file: %s', file)
                            known_status_files = status_files
                        except Exception:
                            log.warn("Could not read maxquant status.")
            log.info("MaxQuant stdout: " + outs.decode())
            log.info("MaxQuant stderr: " + errs.decode())
            ret = mqcall.returncode
            if ret != 0:
                log.error("MaxQuant finished with error code " + str(ret))
                raise RuntimeError("MaxQuant error " + str(ret))
            log.info("MaxQuant finished successfully")

    def run(self):
        try:
            with self.task.beat():
                self._execute_task()
        except Exception:
            self.task.log.exception("Unknown Error.")

    def _execute_task(self):
        log = self.task.log
        log.info("Want to prepare files. Waiting for resources.")

        self.task.status('WAITING')
        if not self.prepare_sem.acquire(timeout=self.sem_timeout):
            msg = "Timeout. No resources available."
            log.error(msg)
            self.task.error(msg)
            return

        try:
            self.task.status('PREPARING FILES')
            #self.task.do_checksums()
            params, datafiles = self._process_params()
            log.info("File preparation finished")
        except Exception as e:
            log.exception("Error while preparing files")
            self.task.error("Error while preparing files: " + str(e))
            return
        finally:
            self.prepare_sem.release()

        log.info("Want to start MaxQuant. Waiting for resources.")
        self.task.status('WAITING')
        if not self.mq_sem.acquire(timeout=self.sem_timeout):
            msg = "Timeout. No resources available."
            log.error(msg)
            self.task.error(msg)
            return

        try:
            self.task.status('RUNNING')
            self._run_maxquant(params, datafiles)
        except Exception as e:
            log.exception("Error running MaxQuant.")
            self.task.error("Error running MaxQuant.")
            return
        finally:
            self.mq_sem.release()


class MQDaemon(object):

    def __init__(self, logger, listendir, mqpath, outdir, tmpdir, **args):

        self.listendir = listendir
        self.log = logger
        self.mqpath = mqpath

        if args.get('timeout', None) is not None:
            self.timeout = args['timeout']
        else:
            self.timeout = 200

        if args.get('mqtimeout', None) is not None:
            self.mqtimeout = args['mqtimeout']
        else:
            self.mqtimeout = None

        if args.get('num_workers', None) is not None:
            self.num_workers = args['num_workers']
        else:
            self.num_workers = 2

        self.listener = fscall.listen(
            listendir=listendir,
            outdir=outdir,
            task_re=args.get('task_re', None),
        )
        self.mq_sem = threading.BoundedSemaphore(self.num_workers)
        self.prepare_sem = threading.BoundedSemaphore(self.num_workers)
        self.tmpdir = tmpdir

    def serve(self, maxtasks=None):
        """ Listen for new tasks in listendir and start worker thread. """
        tasks = []
        for i, task in enumerate(self.listener):
            task_thread = MQJob(
                self.mqpath, task,
                self.prepare_sem, self.mq_sem, self.timeout, self.mqtimeout,
                tmpdir=self.tmpdir,
                name="worker-{}".format(task.uuid),
            )
            task.log.info("Create thread for new task " + task.uuid)
            tasks.append(task_thread)
            task_thread.start()
            if maxtasks is not None and i + 1 >= maxtasks:
                break

        self.log.info('Maximum number of tasks reached. No new tasks will be ' +
                      'started')

        for task in tasks:
            task.join()


def setup_logging(args):
    root = logging.getLogger('')
    root.setLevel(logging.INFO)
    if args.logging_ip:
        socket_handler = logging.handlers.SocketHandler(
            args.logging_ip, args.logging_port
        )
        root.addHandler(socket_handler)
    if args.logfile:
        filehandler = logging.FileHandler(str(args.logfile))
        root.addHandler(filehandler)


def main():
    args = parse_args()
    print("Starting daemon...")
    setup_logging(args)
    logging.info("starting daemon")
    logging.info("listendir is " + str(args.listendir))
    logging.info("timeout is " + str(args.timeout))
    logging.info("num_workers is " + str(args.num_workers))
    logging.info("path to maxquant is " + str(args.mqpath))
    logging.info('output dir is ' + str(args.outdir))
    logging.info('maxtasks is ' + str(args.maxtasks))

    try:
        daemon = MQDaemon(
            logging,
            args.listendir,
            args.mqpath,
            timeout=args.timeout,
            num_workers=args.num_workers,
            outdir=args.outdir,
            tmpdir=args.tmpdir,
        )
        print("Listening in dir " + str(args.listendir))
        logging.info('start to listen in directory ' + str(args.listendir))

        daemon.serve(args.maxtasks)
    except:
        logging.exception("Unexpected exception:")

if __name__ == '__main__':
    main()
