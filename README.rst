========================
mqrun: Automate MaxQuant
========================

Overview
========

MaxQuant is a quantitative proteomics software package that unfortunatly
only runs on Windows and is designed for use with a graphical user interface.
Both make it hard to integrate into a larger workflow.

mqrun consists of four parts, that try to mitigate those problems:

:mod:`mqrun.mqparams`
    This is a small library that converts user supplied json-parameter files
    into the rather peculiar configuration files of MaxQuant and supplies a
    small helper function that calles the MaxQuant executable with this
    configuration. The format of the parameter file is documented in
    :mod:`mqrun.mqparams`. Since the format of the MaxQuant configuration file
    keeps changing, mqparams supports one version of MaxQuant only.

:mod:`mqrun.fscall`
    ``fscall`` is a library that handles requests to another machine, where the
    filesystem is the only communication channel. It handles status messages,
    simple error handling, access to logfiles and a heartbeat that tells the
    client that the server is still working on a request.

:mod:`mqrun.mqdaemon`
    ``mqdaemon`` uses ``fscall`` to provide a server that can run on a Windows
    machine and handles requests for MaxQuant. It includes basic load
    balancing. See ``mqdaemon -h`` for options.

:mod:`mqrun.mqclient`
    ``mqclient`` is a small client library that wraps the ``fscall`` routines
    to provide a convenient interface for programs running on linux (or
    windows) machines, that want to run MaxQuant.


Requirements
============

``mqdaemon`` requires python3.4 and optionally ``PyYAML``. An older python3
version should be fine, if ``pathlib``, ``mock`` and ``argparse`` are
installed. ``mqrun`` is only compatible with MaxQuant 1.4.1.2

The code for the client runs fine on python2.7, and requires ``pathlib``.

Windows installation instructions
=================================

A 64Bit machine is preferred by MaxQuant.

Make sure ``MaxQuant 1.4.1.2``, ``.NET 4.5`` and ``MSFileReader`` are
installed.

Download python 3.4 or newer from python.org (the Windows x86-64 MSI
installer). Make sure the python executables are added to the path.

Open a terminal and execute

.. code:: bash

   pip install mqrun

.. todo::

   Get rid of those error dialogs!

   Add fasta files to Andromeda?

Linux installation instructions
===============================

Open a terminal as root and execute

.. code:: bash

   pip install mqrun


Configuration
=============

TODO: Test and check security

Suppose we have two machines in a network, ``win_host`` and ``linux_host``
running Windows and Linux respectively, and we want to run MaxQuant on
``win_host``, but control it from ``linux_host``. First, we need a shared
directory.

Configure Samba
---------------

You can skip this step if you already have a share between ``win_host`` and
``linux_host``.

Edit ``/etc/samba/smb.conf`` and add a share for ``/mnt/win_share`` along the
lines of this:

.. code::

    [win_share]
    comment = Share for MaxQuant
    path = /mnt/win_share
    valid users = linux_user
    writeable = yes
    public = no

Change the permissions in the share:

.. code:: bash

    cd /mnt/win_share
    mkdir requests
    chmod g+w requests
    chmod g-rx requests
    chmod o-rw requests

and set permissions for the global log file:

.. code:: bash

    touch maxquant.log
    chmod g-rw
    chmod o-rw

Then add a Samba user

.. code:: bash

    sudo smbpasswd -a linux_user


and choose a password ``linux_user_passwd``.

After restarting ``smbd`` with ``service smbd restart`` or ``systemctl restart
smbd`` mount the Samba share on the windows machine with ``Add network drive``
(TODO?) and the credentials ``linux_user`` and ``linux_user_passwd``. It should
now be possible to exchange files between ``win_host`` and ``linux_host``.

.. todo::

   Explain the different users involved

Start mqdaemon
--------------

Open a command line on ``win_host`` and start ``mqdaemon``:

.. code:: bash

    cd Z:
    mqdaemon --mqpath C:\\path\to\MaxQuantDir --logfile maxquant.log requests

You can check other options with

.. code:: bash

   mqdaemon -h

The logfile should contain the line ``INFO:root:start to listen in directory
Z:\\requests``, without any errors after that. The daemon is now running and
waits for requests until stopped by SIGTERM (finish all running tasks) or
SIGINT (abort tasks and set to FAILED). It should be safe to start a new
instance after a few seconds in both cases.

Call MaxQuant from linux_host
=============================

Users who want to run MaxQuant need to have write permission in
``/mnt/win_share/requests``, but should not have the right to list the contents
of that directory (execute and read bit not set), or they can access the data
of different users. ``mqclient`` will create directory names inside
``requests``, that are hard to guess (TODO check this!!) to protect the data
from unpriviliged access. (Possible timing attack??)

Run MaxQuant like this:

.. code:: python

    import mqclient
    import time

    # specify the parameters for MaxQuant
    params = {    # TODO how about something sensible ;-)
        "rawFiles": [
            {
                "name": "input1",
                "params": {
                    "defaults": "default",
                    "variableModifications": [
                        "Oxidation (M)",
                    ]
                }
            },
            {
                "name": "input2",
                "params": {
                    "defaults" :"default",
                }
            }
        "fastaFiles": {
            "fileNames": ["fasta1"],
            "firstSearch": ["fasta1"],
        }
        "globalParams": {
            "defaults": "default",
            "matchBetweenRuns": True
        }
    }

    # Set paths to input files
    fasta_files = {
        "fasta1": "path/to/fasta1"
    }

    raw_files = {
        "input1": "/path/to/input1",
        "input2": "/path/to/input2",
    }

    # Run MaxQuant (future is similar to concurrent.futures.Future)
    future = mqclient.mqrun(
        "/mnt/win_share/requests", params, fasta_files, raw_files
    )
    try:
        while not future.done():
            print(result.status)
            time.sleep(1)
        result = future.result()
    except ValueError:
        print("Invalid parameters")
    except TimeoutError:
        print("Too much workload on win_host or connection lost")
    except Exception:
        print("Something else went wrong")
    else:
        print(result.outfiles)
        print(result.log)
