import unittest
import tempfile
import shutil
import os

from spaghettifs.easygit import EasyGit

class EasyGitTestCase(unittest.TestCase):
    def setUp(self):
        self.repo_path = tempfile.mkdtemp()
        self.eg = EasyGit.new(self.repo_path, bare=True)

    def tearDown(self):
        shutil.rmtree(self.repo_path)

    def test_init(self):
        expected_items = ['branches', 'config', 'objects', 'refs']
        self.assertTrue(set(os.listdir(self.repo_path)), set(expected_items))

    def test_initial_commit(self):
        t = self.eg.new_tree()
        c = self.eg.new_commit()
        c.tree = t
        c.author = "Spaghetti User <noreply@grep.ro>"
        c.message = "initial test commit"
        c.save()

if __name__ == '__main__':
    unittest.main()
