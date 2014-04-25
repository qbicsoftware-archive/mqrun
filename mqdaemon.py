from pathlib import Path
import queue
import threading
import logging
try:
    import yaml

except ImportError:
    yaml = None
import json

import fscall
import mqparams

MAXQUEUE = 5
LISTENDIR = Path()
NUM_WORKERS = 5
TASK_RE = "input\_[a-zA-Z0-9]*"
BEAT_INTERVAL = 2
MQBINPATH = Path('c:/Users/adr/Desktop/MaxQuant/bin/MaxQuantCmd.exe')

logging.basicConfig(
    level=logging.DEBUG,
    filename='daemon.log',
)


def get_files(log, infiles):
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


def run_maxquant(log, infiles, outdir, tmpdir):
    param_file, raw_files, fasta_files = get_files(log, infiles)
    params = parse_param_file(log, param_file)

    try:
        result = mqparams.mqrun(
            MQBINPATH, params, raw_files, fasta_files, outdir, tmpdir
        )
    except:
        raise
    # TODO
    """except mqparams.MQParamError as e:
        log.error("Invalid parameter file: " + str(e))
        raise
    except mqparams.MQRunError as e:
        log.error("Error while runnig MaxQuant: " + str(e))
        raise
        raise
    """

    return result


def fill_queue(task_queue, listener):
    for task in listener:
        task.status("WAITING")
        task._start_beat(BEAT_INTERVAL)
        try:
            logging.info("Add new task to queue: " + task.uuid)
            logging.info("Size of queue is approx " + str(task_queue.size))
            task_queue.put_nowait(task)
        except queue.Full:
            task._stop_beat()
            logging.error("Queue is full. Can't add task " + task.uuid)
            task.error("Compute node overloaded")


def worker(task_queue):
    while True:
        try:
            task = task_queue.get()
            task.status('WORKING')
            task._stop_beat()
            with task.beat(BEAT_INTERVAL):
                # TODO
                #try:
                result = run_maxquant(
                    task.log, task.infiles, task.outdir, task.outdir
                )
                #except Exception as e:
                #    task.error(str(e))
                #else:
                #    task.outfiles = result.outfiles
                #    task.success()
        except Exception as e:
            logging.critical("Unknown error in worker thread: " + str(e))


def main():
    logging.info("Starting daemon")
    logging.info("LISTENDIR is " + LISTENDIR)
    logging.info("MAXQUEUE is " + MAXQUEUE)
    logging.info("NUM_WORKERS is " + NUM_WORKERS)
    logging.info("Path to MaxQuant is " + str(MQBINPATH))
    listener = fscall.listen(
        LISTENDIR,
        task_re=TASK_RE,
    )
    task_queue = queue.Queue(maxsize=MAXQUEUE)
    fill_thread = threading.Thread(
        target=fill_queue,
        name="receive_tread",
        args=(task_queue, listener),
    )
    logging.info('Start to listen in directory ' + LISTENDIR)
    fill_thread.start()

    workers = []
    for i in range(NUM_WORKERS):
        thread = threading.Thread(
            target=worker,
            name="worker-{}".format(i),
            args=(task_queue,),
        )
        workers.append(thread)
        logging.info('Starting worker "{}"'.format(thread.name))
        thread.start()


if __name__ == '__main__':
    main()
