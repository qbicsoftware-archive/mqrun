import argparse
#import subprocess
import textwrap
import os
import sys
import logging
from pathlib import Path
import yaml
import subprocess

from maxquant.mqxml import make_xml_string

log = None
global_log = 'maxquant.log'

mq_exec_path = Path('c:/Users/adr/Desktop/MaxQuant/bin/MaxQuantCmd.exe')

description = textwrap.dedent(
    """
    Run MaxQuant on the files in the given directory.

    It expects a file hierarchy like this (#TODO):

        input_88ebfaa1-2dbe-4a5a-874a-2444bdd411cd
        |-- data.raw
        |-- options.json
        `-- params.json

    or like this:

        input_88ebfaa1-2dbe-4a5a-874a-2444bdd411cd
        |-- data.raw
        |-- options.json
        `-- params.xml


    and will write the output files to the corresponding
    `output_88ebfaa1-2dbe-4a5a-874a-2444bdd411cd`. The progress
    of the computation and eventual errors can be monitored in
    `output_*/maxquant.log`.

    For documentation on the options and param files, see #TODO
    The name of the raw input file is not fixed, but can be
    set in the params file.
    """
)


def prepare_global_logger():
    """ Create global log file for all scripts """
    global log
    log = logging.getLogger("run_maxquant_" + str(os.getpid()))
    log.setLevel(logging.DEBUG)
    fh = logging.FileHandler(global_log)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    fh.setFormatter(formatter)
    fh.setLevel(logging.INFO)
    log.addHandler(fh)


def prepare_logger(outdir):
    """ Create logfile in output dir. """
    global log
    logfile = outdir / 'maxquant.log'
    log.setLevel(logging.DEBUG)
    fh = logging.FileHandler(str(logfile))
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    fh.setFormatter(formatter)
    fh.setLevel(logging.DEBUG)
    log.addHandler(fh)


def prepare_dirs(indir):
    indir = Path(indir)
    try:
        indir = indir.resolve()
    except (OSError, RuntimeError) as e:
        log.critical('invalid input directory: ' + str(indir))
        log.critical('exception is: ' + str(e))
        sys.exit(1)

    if not indir.is_dir():
        log.critical('input dir is not a directory')
        sys.exit(1)

    if not indir.name.startswith("input_"):
        log.critical("invalid input directory, should start with input_: " +
                     str(indir))
        sys.exit(1)

    log.info("input dir is " + str(indir))
    basedir = indir.parent

    uuid = indir.name[len("input_"):]
    outdir = basedir / ("output_" + uuid)
    if outdir.exists():
        log.critical("output dir exists: {}".format(str(outdir)))
        sys.exit(1)

    try:
        outdir.mkdir()
    except OSError:
        log.critical("could not create output dir: " + str(outdir))
        sys.exit(1)

    return indir, outdir, uuid


def make_argparse():
    """ Create help message and parse input dir argument."""
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('input_dir', help="path to the input directory")

    return parser


def parse_yaml(paramfile):
    with paramfile.open('r') as f:
        params = yaml.load(f)

    """
    invalid_params = set(params) - set(default_params) - set(required_params)
    if len(invalid_params):
        raise ValueError("Got invalid params in {}: {}".format(
            paramfile, str(invalid_params)
        ))

    missing_params = set(required_params) - set(params)
    if len(missing_params):
        raise ValueError("Missing params in {}: {}".format(
            paramfile, str(missing_params)
        ))
    """  # TODO

    return params


def create_xml_from_xml(outdir, param_file, raw_files):
    raise NotImplementedError()


def create_xml_from_yaml(outdir, param_file, raw_files):
    mqparams = parse_yaml(param_file)
    return make_xml_string(outdir, mqparams, raw_files)


def run_maxquant(indir, outdir, param_file):
    log.info("starting maxquant")
    popen = subprocess.Popen(
        [str(mq_exec_path), "-mqpar", str(param_file)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    log.info("maxquant stated with pid " + str(popen.pid))
    popen.wait()
    log.info("maxquant terminated with exit code " + str(popen.returncode))
    log.debug("stdout of maxquant:\n" + popen.stdout.read().decode())
    log.debug("stderr of maxquant:\n" + popen.stderr.read().decode())


def main():
    log.info("starting run_maxquant script")
    args = make_argparse().parse_args()
    indir, outdir, uuid = prepare_dirs(args.input_dir)

    try:
        prepare_logger(outdir)
    except Exception as e:
        log.critical("could not initiate local logfile, exiting")
        log.critical("exception was: " + str(e))
        sys.exit(1)

    log.info("Starting log in output dir. UUID is " + uuid)

    raw_files = list(indir.glob("*.raw"))

    if (indir / "params.yaml").exists():
        xml_str = create_xml_from_yaml(
            outdir, indir / "params.yaml", raw_files
        )
    elif (indir / "params.xml").exists():
        xml_str = create_xml_from_xml(outdir, indir / "params.xml", raw_files)
    else:
        log.critical("Could not find parameter file. Exiting")
        sys.exit(1)

    with (outdir / "params.xml").open('xb') as f:
        f.write(xml_str)

    run_maxquant(indir, outdir, outdir / "params.xml")


if __name__ == '__main__':
    prepare_global_logger()
    #try:
    main()
    #except Exception as e:
    #    log.critical("unknown error: " + str(e))
