import unittest
import tempfile
import shutil
from os import path

from gitar.persistence import Repo

test_git_path = path.join(path.dirname(__file__), 'test.git')

class ReadGitTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repodir = path.join(self.tmpdir, path.basename(test_git_path))
        shutil.copytree(test_git_path, self.repodir)
        self.repo = Repo(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

if __name__ == '__main__':
    unittest.main()
