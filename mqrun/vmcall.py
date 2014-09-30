import subprocess
import os
import tempfile
import logging
import argparse
import shutil
import concurrent.futures
import threading
import select
import socketserver
import struct
import pickle
import time
import sys
from os.path import join as pjoin


logger = logging.getLogger('run-maxquant-host')


def prepare_data_image(dest, data_dir, type='ntfs', format='raw', size='+1G'):
    """ Create a disk image containing the data inside data_dir.

    Parameters
    ----------
    dest: str
        path of the image that should be created
    data_dir: str
        directory containing the data that should be copied to
        the image.
    type: str, optional
        filesystem to use in the image. Could be ntfs or vfat
    format: ['qcow2', 'raw'], optional
        format of the image file
    size: str
        either the size of the whole image or if preceded by a `+`,
        the amount of free space in the final image. The size can
        be specified by appending T, G, M or K.

    Example
    -------
    >>> image = prepare_data_image('image.raw', 'path/to/data/dir', size='+5G')

    Notes
    -----
    This uses `virt-make-fs` from guestfs. See the documentation of this
    package for further information.
    """

    if not os.path.isdir(data_dir):
        raise ValueError('Not a directory: %s' % data_dir)
    if os.path.exists(dest):
        raise ValueError('Destination file exists: %s' % dest)

    subprocess.check_call(
        [
            'virt-make-fs',
            '--partition',
            '--type', type,
            '--format', format,
            '--size', size,
            '--',
            data_dir,
            dest,
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    return dest


def extract_from_image(image, dest, path='/', use_tar=False):
    """ Write the contents of disk image `image` to `dest`.

    This can be used while the virtual machine is running.

    Parameters
    ----------
    image: str
        Path to the image from which the files should be extracted
    dest: str
        Path to the destination directory
    path: str, optional
        Path to a directory or file inside the image that should be
        extracted
    use_tar: bool, optional
        If True, do not copy the contents to dest, but create a
        tar file at dest, that contains the contents of path inside
        the image. This only works if path is a directory.
        In this case dest must be a filename, not a directory.
    """
    if not os.path.isfile(image):
        raise ValueError("Image does not exist: %s" % image)
    if not os.path.isdir(dest) and not use_tar:
        raise ValueError("Destination must be a directory: %s" % dest)
    if os.path.exists(dest) and use_tar:
        raise ValueError("Destination exists but output type is tar: %s" % dest)

    if use_tar:
        command = 'tar-out'
    else:
        command = 'copy-out'

    subprocess.check_call(
        [
            'guestfish',
            '--ro',
            '-a', image,
            '-m', '/dev/sda1',
            command,
            path,
            dest,
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )


def create_overlay(dest_path, base_image):
    if os.path.exists(dest_path):
        raise ValueError("Destination path exists: %s" % dest_path)
    if not os.path.isfile(base_image):
        raise ValueError("Base image file not found: %s" % base_image)

    subprocess.check_call(
        [
            'qemu-img',
            'create',
            '-b', base_image,
            '-f', 'qcow2',
            dest_path
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return dest_path


class VMTask:
    def __init__(self, qemu_bin, root_base_image, workdir, keep_images=False):
        """ Configure and run a virtual machine.

        Parameters
        ----------
        qemu_bin: str
            Name or path of the qemu binary. Usually this would be
            'qemu-system-x86_64'
        root_base_image: str
            Path to a read-only image of a boot partitition
        workdir: str
            Directory where to store temporary images and temporary files
        keep_images: bool
            Do not delete temporary images after shutdown

        Examples
        --------
        >>> with VMTask('qemu-system-x86_64', 'root.raw', '/tmp') as vm:
        >>>     vm.add_diskimg('input.raw', ['input.raw'])
        >>>     vm.add_option('cpu', 'host')
        >>>     avm.add_option('smp', sockets=1, cores=10, threads=2)
        >>>     vm.run()
        """
        if not os.path.isdir(workdir):
            raise ValueError("Workdir does not exist: %s" % workdir)
        self._workdir = workdir

        image_path = pjoin(workdir, 'root_image.ovl')
        self._root_image = create_overlay(image_path, root_base_image)
        self._options = [('drive', [], {'file': self._root_image})]
        self._images = {}

        self._qemu_bin = qemu_bin
        self._stopped = False

        self._keep_images = keep_images
        self._use_socket_logging = False

    def add_diskimg(self, name, path, data_files=None, data_path=None,
                    type='ntfs', format='raw', size='+500M', *args, **options):
        """ Create a new disk image and attach it to the VM.

        TODO: change name to path

        Parameters
        ----------
        name: str
            Name of the disk image
        path: str
            Where to store the image
        data_files: list of file paths
            The list of files to copy to the disk image
        data_path: str
            Path to a directory. The content will be copied to the disk.
            You can use only one of `data_path` and `data_files`.
        type: str
            Filesystem format
        format: ['raw', 'qcow2']
            Format of the disk image
        size: str
            Size of the image
        options: dict
            List of options that are passed to qemu about disk. See section
            `drive` in qemu documentation.
        """
        if data_files is not None and data_path is not None:
            raise ValueError(
                "You can use only one of 'data_path' and 'data_files'"
            )

        # the root image is the first one and is not in this list
        if len(self._images) > 3:
            raise ValueError("qemu does not support more than 4 disks")

        if name in self._images:
            raise ValueError("Name of image is not unique: %s" % name)

        if data_path is not None:
            image = prepare_data_image(path, data_path, type, format, size)
        else:
            if data_files is None:
                data_files = []

            datadir = tempfile.mkdtemp()
            try:
                for file in data_files:
                    shutil.copy(file, pjoin(datadir, os.path.split(file)[1]))

                image = prepare_data_image(path, datadir, type, format, size)
            finally:
                shutil.rmtree(datadir)

        if options is None:
            options = {}

        options['file'] = image
        self._options.append(('drive', args, options))
        self._images[name] = image

    def add_option(self, name, *args, **kwargs):
        """ Add a command line argument to the qemu command line.

        For a list of options, see `man qemu`. Underscores in
        the options will be ignored, so that you can use `if_` instead
        of `if` to specify an interface.

        Examples
        --------
        >>> vm = VMTask('qemu-system-x86_64', 'root.raw', '/tmp')
        >>> vm.add_diskimg('input.raw', [])
        >>> vm.add_option('net', 'nic')
        >>> vm.add_option('cpu', 'host')
        >>> vm.add_option('smp', sockets=1, cores=10, threads=2)
        >>> vm.start()
        """
        self._options.append((name, args, kwargs))

    def add_logging(self, socket_file, host_ip, port):
        if self._use_socket_logging:
            raise ValueError('add_logging was called more than once.')
        if os.path.exists(socket_file):
            raise ValueError('Socket file exists: %s' % socket_file)
        self._use_socket_logging = True
        self._socket_file = socket_file

        self.add_option('chardev', 'socket', path=socket_file, id='logging')
        guestfwd = "tcp:{}:{}-chardev:{}".format(host_ip, port, 'logging')
        self.add_option('net', 'nic')
        self.add_option('net', 'user', guestfwd=guestfwd, restrict='on')

    def copy_out(self, image, dest, path='/'):
        """ Extract files from image. """
        if image not in self._images:
            raise ValueError("Could not find disk image: %s" % image)
        extract_from_image(self._images[image], dest, path)

    def run(self):
        """ Start the virtual machine and wait for it to power down.

        If the VMTask._stopped flag is set, the vm will be killed.
        """

        if self._use_socket_logging:
            # prepare the logging socket
            tcpserver = LogRecordSocketReciever(self._socket_file)
            logging_thread = threading.Thread(
                target=tcpserver.serve_until_stopped
            )
            logging_thread.start()
            self._logging_thread = logging_thread
            self._tcpserver = tcpserver

        cmd = [self._qemu_bin]
        for name, args, kwargs in self._options:
            cmd.append('-' + name)
            # remove underscores in options so that we can pass the option
            # 'if' as 'if_'. Otherwise this would be a syntax error
            args = ','.join([s.rstrip('_') for s in args])
            for key, val in kwargs.items():
                left = str(key).rstrip('_').replace('_', '-')
                right = str(val).rstrip('_')
                if args:
                    args = ','.join([args, '='.join([left, right])])
                else:
                    args = '='.join([left, right])
            if args != '':
                cmd.append(args)

        cmd = [item.rstrip('_') for item in cmd]

        self._vm_popen = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE
        )

        while not self._stopped:
            try:
                retcode = self._vm_popen.wait(timeout=1)
                break
            except subprocess.TimeoutExpired:
                pass
        else:
            self._vm_popen.kill()
            out, err = self._vm_popen.communicate()
            if out:
                print(out)
            if err:
                print(err)
            raise RuntimeError("qemu was aborted")
        out, err = self._vm_popen.communicate()
        if out:
            print(out)
        if err:
            print(err)

        if retcode:
            raise ValueError("qemu returned error code %s" % retcode)

    def __exit__(self, *args, **kwargs):
        self._stopped = True
        if hasattr(self, '_tcpserver'):
            self._tcpserver.abort = True
            time.sleep(1.1)
        if hasattr(self, '_vm_popen'):
            self._vm_popen.wait()
        if not self._keep_images:
            for path in self._images.values():
                os.unlink(path)
            os.unlink(self._root_image)
        if hasattr(self, '_socket_file') and os.path.exists(self._socket_file):
            os.unlink(self._socket_file)

    def __enter__(self):
        return self


def maxquant_vm(qemu, infiles, windows_image, **kwargs):
    """ Prepare a virtual machine to run MaxQuant.

    Return an VMTask instance.

    Parameters
    ----------
    qemu: str
        Path to qemu binary or name, if it is in PATH
    infiles: list of str
        Paths to input and parameter files
    windows_image: str
        Path to the windows boot image containing necessary software. This
        is read-only, it will not be changed.
    mqthreads: int, optional
        The number of threads MaxQuant should use.
    sockets: int, optional
        Number of sockets to export to the VM
    cores: int, optional
        Number of cores per socket to export to the VM
    threads: int, optional
        Number of threads per core to export to the VM
    mem: str, optional
        Amount of memory for the VM (format like 5G)
    input_size: str, optional
        Size of the input image
    output_size: str, optional
        Size of the output image
    vm_logging: bool
        Export log records from vm
    """
    args = {
        'sockets': 1,
        'cores': 1,
        'threads': 1,
        'input_size': '+10G',
        'output_size': '50G',
        'display': False,
        'mem': '2G',
        'keep_images': False,
        'vm_logging': True,
    }
    args.update(kwargs)

    vm = VMTask(qemu, windows_image, '.', args['keep_images'])
    try:
        try:
            data_dir = tempfile.mkdtemp()
            tasks = pjoin(data_dir, 'tasks')
            os.mkdir(tasks)
            task = pjoin(tasks, 'task0')
            os.mkdir(task)
            for file in infiles:
                shutil.copy(file, task)

            with open(pjoin(task, 'START'), 'w'):
                pass

            vm.add_diskimg('input', 'input.img', data_path=data_dir,
                           cache='unsafe', size=args['input_size'],
                           if_='virtio', aio='native')
        finally:
            shutil.rmtree(data_dir)

        vm.add_diskimg('output', 'output.img', [], size=args['output_size'],
                       if_='virtio', aio='native', cache='unsafe')
        vm.add_option('enable-kvm')
        vm.add_option('cpu', 'host')
        vm.add_option('m', args['mem'])
        vm.add_option('smp', sockets=args['sockets'], cores=args['cores'],
                      threads=args['threads'])
        if args['vm_logging']:
            vm.add_logging('logging.socket', '10.0.2.100', 8000)

        if args['display']:
            vm.add_option('display', 'gtk')
        else:
            vm.add_option('display', 'none')
        return vm
    except BaseException:
        vm.__exit__()
        raise


# Read logging record from a unix domain socket. qemu redirects a tcp
# stream from the vm to this socket. For details see
# https://docs.python.org/3/howto/logging-cookbook.html#logging-cookbook

class LogRecordStreamHandler(socketserver.StreamRequestHandler):
    def handle(self):
        logger = logging.getLogger('vm_mqdaemon')
        while True:
            chunk = self.connection.recv(4)
            if len(chunk) < 4:
                break
            slen = struct.unpack('>L', chunk)[0]
            chunk = self.connection.recv(slen)
            while len(chunk) < slen:
                chunk = chunk + self.connection.recv(slen - len(chunk))
            obj = pickle.loads(chunk)
            record = logging.makeLogRecord(obj)
            logger.handle(record)


class LogRecordSocketReciever(socketserver.ThreadingMixIn,
                              socketserver.UnixStreamServer):
    allow_reuse_adddress = True

    def __init__(self, socket_file, handler=LogRecordStreamHandler):
        super().__init__(socket_file, handler)
        self.abort = 0
        self.timeout = 1

    def serve_until_stopped(self):
        abort = 0
        while not abort:
            rd, wr, ex = select.select([self.socket.fileno()],
                                       [], [], self.timeout)
            if rd:
                self.handle_request()
            abort = self.abort


def parse_args():
    parser = argparse.ArgumentParser(
        description='Run MaxQuant with in a virtual machine'
    )

    parser.add_argument(
        '--windows-image', '-i', help='Path to the base windows image. Will ' +
        'not be changed', required=True
    )
    parser.add_argument(
        '--qemu', help='Path to qemu binary', default='qemu-system-x86_64'
    )
    parser.add_argument(
        '--mem', help='Amount of memory on on the VM. Format like "5G"',
        default='2G'
    )
    parser.add_argument(
        '--display', help='Show the windows desktop. Needs X11 and gtk',
        default=False, action='store_true'
    )
    parser.add_argument(
        '--sockets', help='Number of sockets to export to windows', default=1,
        type=int
    )
    parser.add_argument(
        '--cores', help='Number of cores per socket to export to windows',
        default=1, type=int
    )
    parser.add_argument(
        '--threads', help='Number of hyper threads per core', default=1,
        type=int
    )
    parser.add_argument(
        '--input-size', help='Size of the input disk image (use +1G if you ' +
        'want 1 gigabyte of free space after the input files have been ' +
        'written)', default='+10G'
    )
    parser.add_argument(
        '--output-size', help='Size of the output image', default='+50G'
    )
    parser.add_argument(
        '--keep-images',
        help='Do not delete temporary disk images after shutdown',
        default=False, action='store_true'
    )
    parser.add_argument(
        '--no-vm-logging', help='Export logging information from the vm',
        default=False, action='store_true'
    )
    parser.add_argument(
        'output_dir', help='Store MaxQuant output in this directory'
    )
    parser.add_argument(
        'params', help='Parameter file. Ether MaxQuant xml, yaml or json',
    )
    parser.add_argument(
        'raw_files', help='List of raw files to use', nargs='+'
    )

    return parser.parse_args()


def main():
    args = vars(parse_args())
    infiles = args['raw_files'] + [args['params']]
    output_dir = args['output_dir']
    del args['raw_files'], args['params'], args['output_dir']
    qemu = args['qemu']
    args['vm_logging'] = not args['no_vm_logging']
    del args['no_vm_logging']
    del args['qemu']

    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    with maxquant_vm(qemu, infiles, **args) as vm:
        with concurrent.futures.ThreadPoolExecutor(1) as ex:
            res = ex.submit(vm.run)
            try:
                res.result()
            finally:
                vm.copy_out('output', output_dir)


if __name__ == '__main__':
    main()
