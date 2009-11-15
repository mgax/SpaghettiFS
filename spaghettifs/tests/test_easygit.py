import unittest
import tempfile
import shutil
import os
from time import time

import dulwich
from support import setup_logger
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

    def test_commit_with_ancestors(self):
        self.eg.commit(author="Spaghetti User <noreply@grep.ro>",
                       message="initial test commit")

        head_id = self.eg.get_head_id()

        self.eg.commit(author="Spaghetti User <noreply@grep.ro>",
                       message="second test commit",
                       parents=[head_id])

        self.assertRaises(AssertionError, self.eg.commit,
                          author="Sneaky <noreply@grep.ro>",
                          message="bad test commit",
                          parents=['asdf'])

        git = dulwich.repo.Repo(self.repo_path)
        git_h = git.head()
        git_c2 = git.commit(git_h)
        self.assertEqual(len(git_c2.get_parents()), 1)
        git_c1 = git.commit(git_c2.get_parents()[0])
        self.assertEqual(git_c1.get_parents(), [])

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
            self.assertEqual(set(t2.keys()), set(['b2', 'b3']))
            self.assertEqual(t2['b3'].data, 'asdf')
        self.eg.commit(author="Spaghetti User <noreply@grep.ro>",
                       message="propagating changes")

        eg2 = EasyGit.open_repo(self.repo_path)
        self.assertEqual(eg2.root['t2']['b3'].data, 'asdf')

    def test_modify_blob(self):
        t1 = self.eg.root
        with t1['t2']['b2'] as b2:
            self.assertNotEqual(b2.data, 'qwer')
            b2.data = 'qwer'
            self.assertEqual(b2.data, 'qwer')

        with t1['t2']['b2'] as b2:
            self.assertEqual(b2.data, 'qwer')

        self.eg.commit(author="Spaghetti User <noreply@grep.ro>",
                       message="propagating changes")

        eg2 = EasyGit.open_repo(self.repo_path)
        self.assertEqual(eg2.root['t2']['b2'].data, 'qwer')

    def test_modify_multiple(self):
        with self.eg.root as root:
            root['t2']['b2'].data = 'new b2'
            with root.new_tree('t3') as t3:
                t3.new_blob('b3').data = 'new b3'
                t3.new_blob('b4').data = 'new b4'
            with root.new_tree('t4') as t4:
                t4.new_blob('b5').data = 'new b5'
            root.new_blob('b6').data = 'new b6'
        self.eg.commit(author="Spaghetti User <noreply@grep.ro>",
                       message="multiple changes")

        eg2 = EasyGit.open_repo(self.repo_path)
        root2 = eg2.root
        self.assertEqual(set(root2.keys()),
                         set(['b1', 't2', 't3', 't4', 'b6']))
        self.assertEqual(root2['b1'].data, 'b1 data')
        self.assertEqual(set(root2['t2'].keys()), set(['b2']))
        self.assertEqual(root2['t2']['b2'].data, 'new b2')
        self.assertEqual(set(root2['t3'].keys()), set(['b3', 'b4']))
        self.assertEqual(root2['t3']['b3'].data, 'new b3')
        self.assertEqual(root2['t3']['b4'].data, 'new b4')
        self.assertEqual(set(root2['t4'].keys()), set(['b5']))
        self.assertEqual(root2['t4']['b5'].data, 'new b5')
        self.assertEqual(root2['b6'].data, 'new b6')

    def test_child_cache(self):
        root = self.eg.root

        t2a = root['t2']
        t2b = root['t2']
        self.assertTrue(t2a is t2b)

        t2a['b2'].data = 'asdf'
        self.assertEqual(t2b['b2'].data, 'asdf')

        b3a = t2a.new_blob('b3')
        b3a.data = 'b3 data'
        b3b = t2b['b3']
        self.assertTrue(b3a is b3b)
        self.assertEqual(b3b.data, 'b3 data')

        t3a = t2a.new_tree('t3')
        t3a.new_blob('b4')
        t3b = t2b['t3']
        self.assertTrue(t3a is t3b)
        self.assertEqual(set(t3b.keys()), set(['b4']))

    def test_remove_entry(self):
        with self.eg.root as t1:
            with t1['t2'] as t2:
                del t2['b2']
            del t1['b1']

        self.eg.commit(author="Spaghetti User <noreply@grep.ro>",
                       message="removing entries")

        eg2 = EasyGit.open_repo(self.repo_path)
        self.assertEqual(eg2.root.keys(), ['t2'])
        self.assertEqual(eg2.root['t2'].keys(), [])

    def test_self_remove_entry(self):
        with self.eg.root as t1:
            t1['t2'].remove()
            t1['b1'].remove()

        self.eg.commit(author="Spaghetti User <noreply@grep.ro>",
                       message="removing entries")

        eg2 = EasyGit.open_repo(self.repo_path)
        self.assertEqual(eg2.root.keys(), [])

    def test_remove_and_fetch_entry(self):
        t1 = self.eg.root
        t2 = t1['t2']
        t1['t2'].remove()
        self.assertRaises(KeyError, t1.__getitem__, 't2')

class DelayedCommit(unittest.TestCase):
    def setUp(self):
        self.repo_path = tempfile.mkdtemp()
        self.eg = EasyGit.new_repo(self.repo_path, bare=True)

    def tearDown(self):
        shutil.rmtree(self.repo_path)

    def test_create_remove_blob(self):
        r = self.eg.root

        r.new_blob('b')
        del r['b']
        r._commit()

        r.new_tree('t')
        del r['t']
        r._commit()

        r.new_tree('t')
        r['t'].new_blob('b')
        r['t']['b'].data = 'asdf'
        del r['t']
        r._commit()


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

    def test_no_with(self):
        r = self.eg.root
        b = r.new_blob('b')
        b.data = 'asdf'

class BranchTestCase(unittest.TestCase):
    def setUp(self):
        self.repo_path = tempfile.mkdtemp()
        self.eg = EasyGit.new_repo(self.repo_path, bare=True)

    def tearDown(self):
        shutil.rmtree(self.repo_path)

    def get_head(self, name):
        ref_path = os.path.join(self.repo_path, 'refs/heads', name)
        with open(ref_path, 'rb') as f:
            return f.read().strip()

    def test_various_commits(self):
        with self.eg.root as r:
            r.new_blob('bl').data = 'asdf'
        self.eg.commit(author="Spaghetti User <noreply@grep.ro>",
                       message="commit on master")
        head1 = self.eg.get_head_id()
        self.assertEqual(head1, self.get_head('master'))

        with self.eg.root as r:
            r['bl'].data = 'qwer'
        self.eg.commit(author="Spaghetti User <noreply@grep.ro>",
                       message="commit on secondary",
                       branch="secondary")
        head2 = self.eg.get_head_id('secondary')
        self.assertEqual(head1, self.get_head('master'))
        self.assertEqual(head2, self.get_head('secondary'))

if __name__ == '__main__':
    setup_logger('ERROR')
    unittest.main()
