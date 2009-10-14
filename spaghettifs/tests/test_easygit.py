import unittest
import tempfile
import shutil
import os
from time import time

import dulwich
from spaghettifs.easygit import EasyGit

class BasicTestCase(unittest.TestCase):
    def setUp(self):
        self.repo_path = tempfile.mkdtemp()
        self.eg = EasyGit.new_repo(self.repo_path, bare=True)

    def tearDown(self):
        shutil.rmtree(self.repo_path)

    def test_init(self):
        expected_items = ['branches', 'config', 'objects', 'refs']
        self.assertTrue(set(os.listdir(self.repo_path)), set(expected_items))

    def test_initial_commit(self):
        self.eg.commit(author="Spaghetti User <noreply@grep.ro>",
                       message="initial test commit")

        git = dulwich.repo.Repo(self.repo_path)
        git_h = git.head()
        git_c = git.commit(git_h)
        self.assertEqual(git_c.author, "Spaghetti User <noreply@grep.ro>")
        self.assertEqual(git_c.message, "initial test commit")
        self.assertEqual(git_c.get_parents(), [])

    def test_commit_with_tree(self):
        t1 = self.eg.root
        t2 = t1.new_tree('t2')
        self.eg.commit(author="Spaghetti User <noreply@grep.ro>",
                       message="test commit with tree")

        git = dulwich.repo.Repo(self.repo_path)
        git_t = git.tree(git.commit(git.head()).tree)
        self.assertEqual(len(git_t.entries()), 1)
        self.assertEqual(git_t.entries()[0][:2], (040000, 't2'))

    def test_commit_with_blob(self):
        t1 = self.eg.root
        b1 = t1.new_blob('b1')
        with b1:
            b1.data = 'hello blob!'
        self.eg.commit(author="Spaghetti User <noreply@grep.ro>",
                       message="test commit with blob")

        git = dulwich.repo.Repo(self.repo_path)
        git_t = git.tree(git.commit(git.head()).tree)
        self.assertEqual(len(git_t.entries()), 1)
        self.assertEqual(git_t.entries()[0][:2], (0100644, 'b1'))
        git_b = git.get_blob(git_t['b1'][1])
        self.assertEqual(git_b.data, "hello blob!")

class RetrievalTestCase(unittest.TestCase):
    def setUp(self):
        self.repo_path = tempfile.mkdtemp()
        git = dulwich.repo.Repo.init_bare(self.repo_path)
        git_t1 = dulwich.objects.Tree()
        git_t2 = dulwich.objects.Tree()
        git_b1 = dulwich.objects.Blob.from_string('b1 data')
        git_b2 = dulwich.objects.Blob.from_string('b2 data')
        git.object_store.add_object(git_b1)
        git.object_store.add_object(git_b2)
        git_t2['b2'] = (0100644, git_b2.id)
        git.object_store.add_object(git_t2)
        git_t1['b1'] = (0100644, git_b1.id)
        git_t1['t2'] = (040000, git_t2.id)
        git.object_store.add_object(git_t1)

        commit_time = int(time())
        git_c = dulwich.objects.Commit()
        git_c.commit_time = commit_time
        git_c.author_time = commit_time
        git_c.commit_timezone = 2*60*60
        git_c.author_timezone = 2*60*60
        git_c.author = "Spaghetti User <noreply@grep.ro>"
        git_c.committer = git_c.author
        git_c.message = "test fixture"
        git_c.encoding = "UTF-8"
        git_c.tree = git_t1.id
        git.object_store.add_object(git_c)
        git.refs['refs/heads/master'] = git_c.id

        self.eg = EasyGit.open_repo(self.repo_path)

    def tearDown(self):
        shutil.rmtree(self.repo_path)

    def test_fetch_objects(self):
        t1 = self.eg.root
        self.assertEqual(set(t1.keys()), set(['b1', 't2']))
        b1 = t1['b1']
        self.assertEqual(b1.data, 'b1 data')
        t2 = t1['t2']
        self.assertEqual(set(t2.keys()), set(['b2']))
        b2 = t2['b2']
        self.assertEqual(b2.data, 'b2 data')

    def test_modify_tree(self):
        t1 = self.eg.root
        with t1['t2'] as t2:
            b3 = t2.new_blob('b3')
            with b3:
                b3.data = 'asdf'
        self.eg.commit(author="Spaghetti User <noreply@grep.ro>",
                       message="propagating changes")

        eg2 = EasyGit.open_repo(self.repo_path)
        self.assertEqual(eg2.root['t2']['b3'].get_data(), 'asdf')

    def test_modify_blob(self):
        t1 = self.eg.root
        with t1['t2']['b2'] as b2:
            b2.set_data('qwer')
        self.eg.commit(author="Spaghetti User <noreply@grep.ro>",
                       message="propagating changes")

        eg2 = EasyGit.open_repo(self.repo_path)
        self.assertEqual(eg2.root['t2']['b2'].get_data(), 'qwer')

class ContextTestCase(unittest.TestCase):
    def setUp(self):
        self.repo_path = tempfile.mkdtemp()
        self.eg = EasyGit.new_repo(self.repo_path, bare=True)

    def tearDown(self):
        shutil.rmtree(self.repo_path)

    def test_nested(self):
        r = self.eg.root
        with r:
            with r:
                with r:
                    self.assertEqual(r._ctx_count, 3)
                self.assertEqual(r._ctx_count, 2)
            self.assertEqual(r._ctx_count, 1)
        self.assertEqual(r._ctx_count, 0)
        self.assertRaises(AssertionError, r.__exit__, None, None, None)

        b = r.new_blob('b')
        with b:
            with b:
                with b:
                    self.assertEqual(b._ctx_count, 3)
                self.assertEqual(b._ctx_count, 2)
            self.assertEqual(b._ctx_count, 1)
        self.assertEqual(b._ctx_count, 0)
        self.assertRaises(AssertionError, b.__exit__, None, None, None)


if __name__ == '__main__':
    unittest.main()
