import unittest
import tempfile
import shutil
import os

import dulwich
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
        self.eg.commit(author="Spaghetti User <noreply@grep.ro>",
                       message="initial test commit",
                       tree=self.eg.new_tree())

        git = dulwich.repo.Repo(self.repo_path)
        git_h = git.head()
        git_c = git.commit(git_h)
        self.assertEqual(git_c.author, "Spaghetti User <noreply@grep.ro>")
        self.assertEqual(git_c.message, "initial test commit")
        self.assertEqual(git_c.get_parents(), [])

    def test_commit_with_tree(self):
        t1 = self.eg.new_tree()
        t2 = self.eg.new_tree()
        with t1:
            t1['t2'] = t2
        self.eg.commit(author="Spaghetti User <noreply@grep.ro>",
                       message="test commit with tree",
                       tree=t1)

        git = dulwich.repo.Repo(self.repo_path)
        git_t = git.tree(git.commit(git.head()).tree)
        self.assertEqual(len(git_t.entries()), 1)
        self.assertEqual(git_t.entries()[0][:2], (040000, 't2'))

if __name__ == '__main__':
    unittest.main()
