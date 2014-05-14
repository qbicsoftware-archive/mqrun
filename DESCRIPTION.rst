MaxQuant is a quantitative proteomics software package that unfortunatly
only runs on Windows and is designed for use with a graphical user interface.
Both make it hard to integrate into a larger workflow.

mqrun consists of four parts, that try to mitigate those problems:

:mod:`mqrun.mqparams`
    This is a small library that converts user supplied json-parameter files
    into the rather peculiar configuration files of MaxQuant and supplies a
    small helper function that calles the MaxQuant executable with this
    configuration. The format of the parameter file is documented in
    :doc:`param_format`. Since the format of the MaxQuant configuration file
    keeps changing, mqparams supports one version of MaxQuant only.

:mod:`mqrun.fscall`
    ``fscall`` is a library that handles requests to another machine, where the
    filesystem is the only communication channel. It provides status messages,
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

    If configured correctly it can also start a virtual machine running Windows
    and use that to run MaxQuant without the need for a dedicated Windows
    machine.
