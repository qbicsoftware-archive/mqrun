
==========
Quickstart
==========

Calling MaxQuant locally
========================

blubb.

Calling MaxQuant on a dedicated Windows machine
===============================================

Suppose the two hosts ``win_host`` and ``linux_host`` are in a network and we
would like to call MaxQuant on the ``win_host``, but control the process and
provide the input and parameter files from the linux machine.

In this tutorial I will assume that MaxQuant is already installed on
``win_host`` and that a share has been setup: ``/mnt/win_share`` should be
accessable from ``win_host`` as ``Z:\\``. There are countless tutorials for
this setup, but you can find a quick description for this in (:todo:`not yet`).

First we need to install python3.3 or later on the windows machine. Download
the msi installer from `the Python download page
<https://www.python.org/downloads/windows/>`_ and install Python. For ease of
use, the option to add the executables to the PATH should be enabled.
(:todo:`check that this option exists...`)

Next, install ``mqrun`` on both machines:

.. code::

    pip install mqrun

On linux this needs administrator priviliges, although a local installation
with `virtualenv <http://www.virtualenv.org/en/latest/>`_ is possible.

.. note::

   python2.7 is ok on linux, the windows version needs at least python3.3

Start the :mod:`mqrun.mqdaemon` server process on the windows machine:

.. code::

   cd Z:
   mkdir requests
   mqdaemon -h  # have a look at the options...
   mqdaemon --mqpath C:\\path\to\MaxQuant\dir --logfile maxquant.log requests

You can now run MaxQuant from linux (using python):

.. code:: python

   from mqrun import mqclient
   import json

   with open('paramfile.json') as f:
       params = json.load(f)

   path_data = {
       "raw_file1": "/path/to/raw/file",
       "raw_file2": "/path/to/raw/file2",
       "fasta_file": "/path/to/fasta/file",
   }

   maxquant = mqclient.mqrun(params, path_data, share='/mnt/win_share_requests')

   maxquant.wait()
   try:
       outfiles = maxquant.result()
   except TimeoutError:
       print("Connection lost or server overloaded")
   except Exception as e:
       print("Error executing MaxQuant: " + str(e))
   else:
       print(outfiles)

   print("Logfile\n=======\n")
   print(maxquant.log)  # print the logging output of the server

The format of the parameter file is explained in :mod:`mqrun.mqparams`.


Use MaxQuant on an virtual machine
==================================


Requirements:

- qemu with kvm enabled on the linux machine

- guestfs + python wrappers on linux

- A windows virtual machine image


Configure the windows machine
-----------------------------

Start the windows machine with qemu and the software image at (TODO)

.. code:: bash

   qemu -hda winvm.img -boot c -hdb mqrun_image.img -enable-kvm -m 1024

and execute the file ``install.bat`` on ``d:\\``.

Execute MaxQuant exactly as in the example above, but replace the keyword
argument ``share`` in the ``mqclient.mqrun`` call by ``img=path/to/win/image``.
