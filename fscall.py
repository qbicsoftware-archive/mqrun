from pathlib import Path
import logging
import time
import contextlib
import threading
from datetime import datetime
import re
from uuid import uuid4


def listen(listen_dir, maxqueue=0, task_re=None, interval=2):
    listen_dir = Path(listen_dir).resolve()
    if not listen_dir.is_dir():
        raise ValueError("Can only listen in a directory")
    while True:
        logging.debug("looking for new tasks in dir " + str(listen_dir))
        dirs = [dir for dir in listen_dir.iterdir() if dir.is_dir()]
        for dir in dirs:
            if task_re and not re.match(task_re, dir.name):
                logging.debug("skipping dir {}, does not match re"
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
                except ImportError as e:  # TODO set exception
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
            if p.is_file() and p.name not in ["START", "STARTED"]
        )

        self._prepare_logger()
        self.log.info("Starting log in task-local logfile")

        try:
            (dir / "output").mkdir()
        except FileExistsError:
            raise ValueError("Output directory exists")

        self._outdir = dir / "output"

        self._beat_file = dir / "BEAT"
        if self._beat_file.exists():
            self.log.warn("Overwriting BEAT-file")

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
        self._write_file("SUCCESS")
        self.log.info("successfully finished task")
        self._stop_beat()

    def error(self, message=None):
        self._stop_beat()
        self.log.error("Task failed. Message was: " + message)
        self._write_file("FAILED", message)

    def status(self, status):
        self._write_file("STATUS", status)
        self.log.info("switched status to " + status)

    def _write_file(self, filename, message):
        pass

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
