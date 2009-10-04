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
        self.repo = Repo(self.repodir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_get_file(self):
        a = self.repo.get_file('/a.txt')
        self.assertEqual(a.name, 'a.txt')
        self.assertEqual(a.data, 'text file "a"\n')

    def test_list_files(self):
        ls = self.repo.list_files('/')
        self.assertEqual(ls, ['a.txt'])

if __name__ == '__main__':
    unittest.main()
