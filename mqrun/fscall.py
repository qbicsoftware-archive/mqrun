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
