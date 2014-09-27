from mqrun.vmcall import *
import tempfile
import os
from os.path import join as pjoin
from os.path import exists as pexists
import shutil
import subprocess
from nose.tools import *


class TestDataImage():
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def _prepare_data(self):
        data = pjoin(self.tmpdir, 'data')
        os.mkdir(data)
        with open(pjoin(data, 'testfile'), 'w') as f:
            f.write('hi')
        return data

    def test_exists(self):
        image = pjoin(self.tmpdir, 'image.img')
        data = self._prepare_data()
        prepare_data_image(image, data, size="20M")
        assert pexists(image)

    @raises(subprocess.CalledProcessError)
    def test_invalid_type(self):
        image = pjoin(self.tmpdir, 'image.img')
        data = self._prepare_data()
        prepare_data_image(image, data, type="no_such_fs_type")

    @raises(subprocess.CalledProcessError)
    def test_invalid_size(self):
        image = pjoin(self.tmpdir, 'image.img')
        data = self._prepare_data()
        prepare_data_image(image, data, size="5gb")

    def test_read_dir(self):
        image = pjoin(self.tmpdir, 'image.img')
        data = self._prepare_data()
        prepare_data_image(image, data, size="20M")
        outdir = pjoin(self.tmpdir, 'outdir')
        os.mkdir(outdir)
        extract_from_image(image, outdir)
        with open(pjoin(outdir, 'testfile')) as f:
            assert f.read() == 'hi'

    def test_read_file(self):
        image = pjoin(self.tmpdir, 'image.img')
        data = self._prepare_data()
        prepare_data_image(image, data, size="20M")
        outdir = pjoin(self.tmpdir, 'outdir')
        os.mkdir(outdir)
        extract_from_image(image, outdir, path='/testfile')
        with open(pjoin(outdir, 'testfile')) as f:
            assert f.read() == 'hi'

    def test_tar_out(self):
        image = pjoin(self.tmpdir, 'image.img')
        data = self._prepare_data()
        prepare_data_image(image, data, size="20M")
        outdir = pjoin(self.tmpdir, 'outdir')
        os.mkdir(outdir)
        outfile = pjoin(outdir, "out.tar")
        extract_from_image(image, outfile, path='/', use_tar=True)
        assert pexists(outfile)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)


class TestCreateOverlay():
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.base_image = pjoin(self.tmpdir, 'base_image.img')
        self.image = pjoin(self.tmpdir, 'image.ovl')

    def _prepare_base_image(self):
        data = pjoin(self.tmpdir, 'data')
        os.mkdir(data)
        with open(pjoin(data, 'testfile'), 'w') as f:
            f.write('hi')
        image = prepare_data_image(self.base_image, data, size="50M")
        return image

    def test_exists(self):
        base_image = self._prepare_base_image()
        create_overlay(self.image, base_image)
        assert pexists(base_image)
        assert pexists(self.image)
