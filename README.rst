========================
mqrun: Automate MaxQuant
========================

See `documentation <http://mqrun.rtfd.org>`_

Overview
========

MaxQuant is a quantitative proteomics software package that unfortunatly
only runs on Windows and is designed for use with a graphical user interface.
Both make it hard to integrate into a larger workflow.

mqrun consists of three parts, that try to mitigate those problems:

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


Requirements
============

``mqdaemon`` is compatible with >= python3.3 and needs MaxQuant 1.5.0.0

The code for the client runs fine on python2.7.


Installation instructions
=========================

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

Create a directory for the requests

.. code:: bash

    cd /mnt/win_share
    mkdir requests

Then add a Samba user

.. code:: bash

    sudo smbpasswd -a linux_user


and choose a password ``linux_user_passwd``.

After restarting ``smbd`` with ``service smbd restart`` or ``systemctl restart
smbd`` mount the Samba share on the windows machine with ``Add network drive``
(TODO?) and the credentials ``linux_user`` and ``linux_user_passwd``. It should
now be possible to exchange files between ``win_host`` and ``linux_host``.

Start mqdaemon
--------------

Open a command line on ``win_host`` and start ``mqdaemon``:

.. code:: bash

    Z:
    mqdaemon --mqpath C:\\path\to\MaxQuantDir --logfile maxquant.log requests

You can check other options with

.. code:: bash

   mqdaemon -h

The logfile should contain the line ``INFO:root:start to listen in directory
Z:\\requests``, without any errors after that. The daemon is now running and
waits for requests until stopped by SIGTERM (finish all running tasks) or
SIGINT (abort tasks and set to FAILED) (TODO: not properly implemented).
It should be safe to start a new instance after a few seconds in both cases.

Call MaxQuant from linux_host
=============================

Users who want to run MaxQuant need to have write permission in
``/mnt/win_share/requests``, but should not have the right to list the contents
of that directory (execute and read bit not set), or they can access the data
of different users. ``mqclient`` will create directory names inside
``requests``, that are hard to guess (TODO check this!!) to protect the data
from unpriviliged access.

Run MaxQuant like this:

.. code:: python

    import mqclient
    import time
    import json

    # specify the parameters for MaxQuant
    params = {    # TODO how about something sensible ;-)
        # each elemet corresponds to a "parameter group" in MaxQuant
        "rawFiles": [
            {
                "files": [
                    {
                        "name": "input1",
                        "fraction": 1
                    }
                ],
                "params": {
                    "defaults": "default",
                    "variableModifications": [
                        "Oxidation (M)",
                    ]
                }
            }
        ],
        "fastaFiles": {
            "fileNames": ["fasta1"],
            "firstSearch": [],
        }
        "globalParams": {
            "defaults": "default",
            "matchBetweenRuns": True
        }
    }

    with open("path/to/params.json", 'w') as f:
        json.dump(params, f)

    # paths to the input and parameter files
    file_paths = [
        "path/to/fasta1.fasta",
        "path/to/input1.raw",
        "path/to/params.json",
    }

    # Run MaxQuant (future is similar to concurrent.futures.Future)
    future = fscall.submit(
        "/mnt/win_share/requests", file_paths
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
