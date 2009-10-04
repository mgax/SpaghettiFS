import unittest
import tempfile
import shutil
from os import path

from guitar.persistence import Repo

test_git_path = path.join(path.dirname(__file__), 'test.git')

class GuitarTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_path = path.join(self.tmpdir, path.basename(test_git_path))
        shutil.copytree(test_git_path, self.repo_path)
        self.repo = Repo(self.repo_path)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
