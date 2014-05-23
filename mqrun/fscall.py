from pathlib import Path
import logging
import time
import contextlib
import threading
from datetime import datetime
import re
from uuid import uuid4
import hashlib
import os
import tempfile
import shutil


try:
    TimeoutError
except:
    class TimeoutError(OSError):
        pass


def listen(listendir, maxqueue=0, task_re=None, interval=2):
    """ Return a generator of new tasks in listendir """
    listendir = Path(listendir).resolve()
    if not listendir.is_dir():
        raise ValueError("Can only listen in a directory")
    while True:
        logging.debug("Look for new tasks in dir " + str(listendir))
        dirs = [dir for dir in listendir.iterdir() if dir.is_dir()]
        for dir in dirs:
            if task_re and not re.fullmatch(task_re, dir.name):
                logging.debug("Skip dir {}, does not match re"
                              .format(str(dir)))
                continue
            if (dir / "START").exists():
                try:
                    with (dir / "STARTED").open('x'):
                        pass
                except FileExistsError:
                    continue
                logging.info("New task in dir " + str(dir))
                try:
                    task = FSRequest(dir)
                except Exception as e:
                    logging.error("Could not create Task: " + str(e))
                else:
                    yield task
        time.sleep(interval)


class FSRequest(object):
    @property
    def uuid(self):
        return self._uuid

    @property
    def infiles(self):
        return self._infiles

    @property
    def outfiles(self):
        return self._outfile

    @property
    def log(self):
        return self._log

    @property
    def outdir(self):
        return self._outdir

    def __init__(self, dir, uuid=None):

        self._dir = dir

        self._uuid = uuid
        if uuid is None:
            self._uuid = str(uuid4())

        self._infiles = list(
            p for p in dir.glob('**/*')
            if (p.is_file() and
                p.name not in ["START", "STARTED"] and
                p.suffix.lower() not in ['.sha', '.md5'])
        )

        self._prepare_logger()
        self.log.info("Create new task for {} with uuid {}"
                      .format(self._dir, self._uuid))
        self.log.info("Start log in task-local logfile")

        try:
            (dir / "output").mkdir()
        except FileExistsError:
            raise ValueError("Output directory exists")

        self._outdir = dir / "output"

        self._beat_file = dir / "BEAT"
        if self._beat_file.exists():
            self.log.warn("Overwrite BEAT-file")

    def do_checksums(self):
        """ Compute checksums of input files and check if possible. """
        for file in self.infiles:
            check_checksum(self.log, file)

    def _prepare_logger(self):
        logfile = self._dir / "logfile.txt"
        if logfile.exists():
            logging.warning("logfile already exists")
        self._log = logging.getLogger("Task_{}".format(self.uuid))
        self._log.setLevel(logging.DEBUG)
        fh = logging.FileHandler(str(logfile))
        formatter = logging.Formatter(logging.BASIC_FORMAT)
        fh.setFormatter(formatter)
        fh.setLevel(logging.DEBUG)
        self._log.addHandler(fh)

    @contextlib.contextmanager
    def beat(self, interval=5):
        self._start_beat(interval=interval)
        yield
        self._stop_beat()

    def success(self, message=None):
        self._write_file("SUCCESS", message)
        self.log.info("Successfully finished task")
        self._stop_beat()
        self.status('SUCCESS')

    def error(self, message=None):
        self._stop_beat()
        self.log.error("Task failed. Message was: " + message)
        self._write_file("FAILED", message)
        self.status('FAILED')

    def status(self, status):
        self._write_file("STATUS", status)
        self.log.info("Switch to status " + status)

    def _write_file(self, filename, message):
        try:
            with (self._dir / filename).open('w') as f:
                if message is not None:
                    f.write(message)
        except (IOError, OSError) as f:
            self.log.critical("Can not write status file " + str(filename))

    def _start_beat(self, interval):
        self._stop_beating_flag = False

        def beat():
            while not self._stop_beating_flag:
                self._single_beat()
                time.sleep(interval)

        threading.Thread(target=beat).start()

    def _stop_beat(self):
        self._stop_beating_flag = True

    def _single_beat(self):
        with self._beat_file.open('a') as f:
            f.write(datetime.now().isoformat() + '\n')


def checksum(file):
    sha = hashlib.sha256()

    with file.open('rb') as f:
        while True:
            block = f.read(sha.block_size * 1024)
            if not block:
                break
            sha.update(block)

    return sha.hexdigest()


def check_checksum(logger, file):
    logger.info("Compute checksum of " + str(file))
    try:
        sum = checksum(file)
    except OSError:
        logger.error("Error while computing checksum of " + str(file))
        raise

    logger.info("Checksum of file {} is {}".format(file, sum))

    checksum_file = file.with_suffix('.sha')

    try:
        with checksum_file.open() as f:
            lines = f.readlines()
    except OSError:
        logger.warn("No checksum file for " + str(file))
        return

    lines = [line for line in lines if line.strip() != ""]

    if not len(lines) == 1:
        logger.error("Invalid checksum file: " + str(checksum_file))
        raise ValueError("Invalid checksum")

    good_sum = lines[0].split()[0].strip()

    if sum != good_sum:
        logger.error(("Checksums for file {} do not match. " +
                     "Should be {} but is {}")
                     .format(file, good_sum, sum))
        raise ValueError("Invalid checksum")


def basic_file_check(log, file, basedir):
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


def submit(serverdir, infiles, beat_timeout=None):
    """ Submit a new job for a fscall server listening in ``serverdir``.

    Create a new directory in ``serverdir`` and copy the input files
    inside. Wait at most ``beat_timeout`` seconds for an answer of the
    server. Fail if no beat is registered for more than ``beat_timeout``
    seconds. ``submit`` is non-blocking, it returns a ``fscall.Future``
    object, that implements the interface of ``concurrent.futures.Future``.
    """

    future = FSFuture(serverdir, infiles)
    future._start()
    return future


class FSFuture:
    """
    ``FSFuture`` encapsulates a background process that is executed on
    a remote server.

    It implements the ``concurrent.futures.Future`` interface, but does
    not support cancelling. Additional attributes:

    status: str
        The status of the task. Could be "COPYING" or "RUNNING"
    log: str
        The logfile of the remote process so far.
    """
    def __init__(self, serverdir, infiles, beat_timeout=None, timeout=None):
        try:
            self._serverdir = Path(serverdir).resolve()
        except OSError:
            raise ValueError("invalid serverdir: " + str(serverdir))

        try:
            self._orig_infiles = [Path(file).resolve() for file in infiles]
        except OSError:
            raise ValueError("invalid input file")

        self._uuid = str(uuid4())
        self._create_workdir()
        self._status = 'NOT STARTED'
        self._worker = threading.Thread(
            target=self._run, name="fscall_worker_" + self._uuid
        )
        self._finished = threading.Event()
        self._callbacks = []
        self._callback_lock = threading.Lock()
        self._beat_timeout = beat_timeout if beat_timeout is not None else 30
        self._timeout = timeout if timeout is not None else 30

    def _start(self):
        self._worker.start()

    def _run(self):
        try:
            self._infiles = self._copy_infiles(self._orig_infiles)
        except Exception as e:
            self._result = None
            self._exception = e
            self._finished.set()
            return

        try:
            self._start_computation()
        except Exception as e:
            self._result = None
            self._exception = e
            self._finished.set()
            return

        result, exception = self._listen_complete()
        self._result = result
        self._exception = exception
        self._finished.set()

    def _create_workdir(self):
        try:
            self._workdir = tempfile.mkdtemp(
                self._uuid, dir=str(self._serverdir)
            )
        except OSError:
            raise RuntimeError("Could not create temporary directory")

    def _copy_infiles(self, infiles):
        self._status = 'COPY FILES'
        for file in infiles:
            shutil.copy(str(file), str(self._workdir))

    def _start_computation(self):
        self._touch('START')
        start_time = time.time()
        while time.time() - start_time < self._timeout:
            time.sleep(1)
            if self._exists('STATUS', 'BEAT', 'STARTED'):
                self._status = self._read('STATUS')
                self._last_beat = self._get_beat()
                break
        else:
            raise TimeoutError("Server not responding")

    def _listen_complete(self):
        try:
            while True:
                if not self._next_beat():
                    raise TimeoutError("Lost heartbeat. Server down?")
                self._status = self._read('STATUS')
                if self._exists('FAILED'):
                    msg = self._read('FAILED')
                    return None, Exception(msg)
                if self._exists('SUCCESS'):
                    return os.path.join(self._workdir, 'output'), None
        except Exception as e:
            return None, e

    def _touch(self, filename):
        with open(os.path.join(self._workdir, filename), 'w'):
            pass

    def _read(self, filename):
        with open(os.path.join(self._workdir, filename)) as f:
            return f.read()

    def _exists(self, *filenames):
        return all(os.path.exists(os.path.join(self._workdir, name))
                   for name in filenames)

    def _get_beat(self):
        for _ in range(10):
            try:
                beat = self._read('BEAT').split('\n')[-2]
                return datetime.strptime(beat, "%Y-%m-%dT%H:%M:%S.%f")
            except Exception:
                time.sleep(self._beat_timeout / 3.)
        else:
            raise TimeoutError("Could not get beat from server")

    def _next_beat(self):
        time.sleep(self._beat_timeout)

        try:
            beat = self._get_beat()
        except Exception:
            return False

        if not (beat - self._last_beat).total_seconds() > 0:
            return False

        self._last_beat = beat
        return True

    @property
    def log(self):
        return self._read('logfile.txt')

    @property
    def status(self):
        return self._status

    def done(self):
        return self._finished.is_set()

    def cancel(self):
        raise NotImplementedError()

    def cancelled(self):
        return False

    def running(self):
        return not self._finished.is_set()

    def result(self, timeout=None):
        if not self._finished.wait(timeout=timeout):
            raise TimeoutError()
        if self._exception is not None:
            raise self._exception
        return self._result

    def exception(self, timeout=None):
        if not self._finished.wait(timeout=timeout):
            raise TimeoutError()
        return self._exception

    def add_done_callback(self, fn):
        def wrap_fn():
            self._finished.wait()
            fn(self)
        threading.Thread(target=wrap_fn).start()
