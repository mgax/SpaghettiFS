from os import path
import unittest
import tempfile
import shutil
import random
import json

import dulwich

from support import SpaghettiTestCase, setup_logger, randomdata
from spaghettifs.storage import GitStorage, FeatureBlob
from spaghettifs import treetree

class BackendTestCase(SpaghettiTestCase):
    def test_walk(self):
        root = self.repo.get_root()
        self.assertTrue(root.is_dir)
        self.assertEqual(set(root.keys()), set(['a.txt', 'b']))
        self.assertRaises(KeyError, lambda: root['nonexistent'])

        a_txt = root['a.txt']
        self.assertFalse(a_txt.is_dir)
        self.assertEqual(a_txt.name, 'a.txt')
        self.assertEqual(a_txt.size, 14)
        self.assertEqual(a_txt._read_all_data(), 'text file "a"\n')
        self.assertEqual(a_txt.path, '/a.txt')

        b = root['b']
        self.assertTrue(b.is_dir)
        self.assertEqual(set(b.keys()), set(['c', 'f.txt']))
        self.assertEqual(b.path, '/b/')

        c = b['c']
        self.assertTrue(c.is_dir)
        self.assertEqual(set(c.keys()), set(['d.txt', 'e.txt']))
        self.assertEqual(c.path, '/b/c/')

        d = c['d.txt']
        self.assertEqual(d.path, '/b/c/d.txt')

    def test_create_file(self):
        b = self.repo.get_root()['b']
        g_txt = b.create_file('g.txt')
        self.assertFalse(g_txt.is_dir)
        self.assertEqual(g_txt.size, 0)
        self.assertEqual(g_txt._read_all_data(), '')
        self.assertEqual(g_txt.name, 'g.txt')

        repo2 = GitStorage(self.repo_path)
        g_txt_2 = repo2.get_root()['b']['g.txt']
        self.assertFalse(g_txt_2.is_dir)
        self.assertEqual(g_txt_2.size, 0)
        self.assertEqual(g_txt_2._read_all_data(), '')
        self.assertEqual(g_txt_2.name, 'g.txt')

    def test_write_file_data(self):
        def assert_git_contents(data):
            repo2 = GitStorage(self.repo_path)
            h_txt_2 = repo2.get_root()['b']['h.txt']
            self.assertEqual(h_txt_2.size, len(data))
            self.assertEqual(h_txt_2._read_all_data(), data)

        b = self.repo.get_root()['b']
        h_txt = b.create_file('h.txt')
        h_txt.write_data('hello git!', 0)
        self.assertEqual(h_txt.size, 10)
        self.assertEqual(h_txt._read_all_data(), 'hello git!')
        assert_git_contents('hello git!')

        h_txt.write_data(':)', 13)
        self.assertEqual(h_txt.size, 15)
        self.assertEqual(h_txt._read_all_data(), 'hello git!\0\0\0:)')
        assert_git_contents('hello git!\0\0\0:)')

        h_txt.truncate(17)
        self.assertEqual(h_txt.size, 17)
        self.assertEqual(h_txt._read_all_data(), 'hello git!\0\0\0:)\0\0')
        assert_git_contents('hello git!\0\0\0:)\0\0')

        h_txt.truncate(5)
        self.assertEqual(h_txt.size, 5)
        self.assertEqual(h_txt._read_all_data(), 'hello')
        assert_git_contents('hello')

        h_txt.write_data('-there', 5)
        self.assertEqual(h_txt.size, 11)
        self.assertEqual(h_txt._read_all_data(), 'hello-there')
        assert_git_contents('hello-there')

    def test_remove_file(self):
        c = self.repo.get_root()['b']['c']
        self.assertEqual(set(c.keys()), set(['d.txt', 'e.txt']))

        d_txt = c['d.txt']
        d_txt.unlink()
        self.assertEqual(set(c.keys()), set(['e.txt']))

        repo2 = GitStorage(self.repo_path)
        c_2 = repo2.get_root()['b']['c']
        self.assertEqual(set(c_2.keys()), set(['e.txt']))

    def test_make_directory(self):
        c = self.repo.get_root()['b']['c']
        x = c.create_directory('x')
        self.assertEqual(set(c.keys()), set(['d.txt', 'e.txt', 'x']))

        repo2 = GitStorage(self.repo_path)
        c_2 = repo2.get_root()['b']['c']
        self.assertEqual(set(c_2.keys()), set(['d.txt', 'e.txt', 'x']))

        y = x.create_file('y')
        y.write_data('ydata', 0)
        self.assertEqual(set(x.keys()), set(['y']))
        self.assertEqual(y._read_all_data(), 'ydata')

        repo3 = GitStorage(self.repo_path)
        c_3 = repo3.get_root()['b']['c']
        self.assertEqual(set(c_3.keys()), set(['d.txt', 'e.txt', 'x']))
        x_3 = c_3['x']
        self.assertEqual(set(x_3.keys()), set(['y']))
        y_3 = x_3['y']
        self.assertEqual(y_3._read_all_data(), 'ydata')

        x.unlink()

        repo4 = GitStorage(self.repo_path)
        c_4 = repo4.get_root()['b']['c']
        self.assertEqual(set(c_4.keys()), set(['d.txt', 'e.txt']))

    def test_empty_directory(self):
        c = self.repo.get_root()['b']['c']
        x = c.create_directory('x')
        x.create_file('f')
        x['f'].unlink()
        self.assertEqual(set(x.keys()), set())

    def test_30_files(self):
        b = self.repo.get_root()['b']
        g = b.create_directory('g')
        for c in xrange(30):
            f = g.create_file('f_%d' % c)
            f.write_data('file contents %d' % c, 0)

        repo2 = GitStorage(self.repo_path)
        g2 = repo2.get_root()['b']['g']
        for c in xrange(30):
            f2 = g2['f_%d' % c]
            self.assertEqual(f2._read_all_data(), 'file contents %d' % c)

    def test_dangerous_filenames(self):
        g = self.repo.get_root()['b'].create_directory('g')
        h = self.repo.get_root()['b'].create_directory('h')
        fail_names = ['.', '..', '/', '', 'as/df', 'x'*256]
        ok_names = [' ', 'ab ', ' cd', 'as\0df', 'qwe\tr', 'zc\nvb', '"', "'",
                    '(', ')', '-', '+', '\\', '=', '?', '*', '.x', '..x',
                    'x'*255]

        for name in fail_names:
            self.assertRaises(ValueError, g.create_file, name)
            self.assertRaises(ValueError, h.create_directory, name)

        for name in ok_names:
            g.create_file(name).write_data(repr(name*2), 0)
            d = h.create_directory(name)
            d.create_file('afile')
            d.create_directory('adir')

        self.assertEqual(set(ok_names), set(g.keys()))
        self.assertEqual(set(ok_names), set(h.keys()))
        for name in ok_names:
            self.assertEqual(g[name]._read_all_data(), repr(name*2))
            g[name].unlink()
            self.assertEqual(set(h[name].keys()), set(['afile', 'adir']))
            h[name]['afile'].unlink()
            h[name]['adir'].unlink()
            self.assertEqual(list(h[name].keys()), [])
            h[name].unlink()

        self.assertEqual(list(h.keys()), [])

    def test_read_past_eof(self):
        a_txt = self.repo.get_root()['a.txt']

        try:
            data = a_txt.read_data(0, 1024)
        except Exception, e:
            self.fail('read past EOF raised %r' % e)
        self.assertEqual(data, 'text file "a"\n')

        try:
            data = a_txt.read_data(500, 100)
        except Exception, e:
            self.fail('read past EOF raised %r' % e)
        self.assertEqual(data, '')

    def test_hardlink(self):
        root = self.repo.get_root()
        a = root['a.txt']
        self.assertEqual(a.inode['nlink'], 1)

        linked_a = root['b'].link_file('linked_a.txt', a)
        self.assertTrue(id(a.inode) == id(linked_a.inode),
                        "different inodes for `a` and `linked_a`")
        self.assertEqual(a.inode['nlink'], 2)

        a.write_data('new data for text file "a"', 0)
        self.assertEqual(linked_a._read_all_data(),
                         'new data for text file "a"')

        repo2 = GitStorage(self.repo_path)
        a_2 = repo2.get_root()['a.txt']
        linked_a_2 = repo2.get_root()['b']['linked_a.txt']
        self.assertTrue(id(a_2.inode) == id(linked_a_2.inode))
        self.assertEqual(a_2.inode['nlink'], 2)
        self.assertEqual(linked_a_2._read_all_data(),
                         'new data for text file "a"')

        a.unlink()
        self.assertEqual(linked_a.inode['nlink'], 1)

        inode_name = linked_a.inode.name
        inodes_tt = treetree.TreeTree(self.repo.eg.root['inodes'], prefix='it')
        self.assertTrue(inode_name[1:] in inodes_tt)
        try:
            self.repo.get_inode(inode_name)
        except KeyError:
            self.fail()

        linked_a.unlink()
        self.assertFalse(inode_name in self.repo.eg.root['inodes'])
        self.assertRaises(KeyError, self.repo.get_inode, inode_name)

class LargeFileTestCase(SpaghettiTestCase):
    large_data = randomdata(1024 * 1024) # 1 MB

    def assert_file_contents(self, reference):
        repo2 = GitStorage(self.repo_path)
        f = repo2.get_root()['b']['f']
        self.assertEqual(f._read_all_data(), reference,
                         '`f._read_all_data()` and `reference` do not match')

    def test_store(self):
        f = self.repo.get_root()['b'].create_file('f')
        f.write_data(self.large_data, 0)
        self.assert_file_contents(self.large_data)

    def test_write_chunks(self):
        f = self.repo.get_root()['b'].create_file('f')
        block_size = 64*1024 # 64 KB
        for offset in xrange(0, len(self.large_data), block_size):
            f.write_data(self.large_data[offset:offset + block_size], offset)
        self.assert_file_contents(self.large_data)

    def test_write_random(self):
        f = self.repo.get_root()['b'].create_file('f')
        block_size = 39 * 1024 # 39 KB
        offsets = range(0, len(self.large_data), block_size)
        random.shuffle(offsets)
        for offset in offsets:
            f.write_data(self.large_data[offset:offset + block_size], offset)
        self.assert_file_contents(self.large_data)

    def test_truncate(self):
        f = self.repo.get_root()['b'].create_file('f')
        f.write_data(self.large_data[:877*1024], 0)
        f.truncate(400*1024)
        self.assert_file_contents(self.large_data[:400*1024])
        f.write_data(self.large_data[400*1024:], 400*1024)
        self.assert_file_contents(self.large_data)

    def test_write_at_boundaries(self):
        # TODO: don't assume a 64 KB block size
        kb64 = 64*1024
        b = self.repo.get_root()['b']

        f = b.create_file('f')
        f.write_data('', 0)
        self.assert_file_contents('')
        f.unlink()

        f = b.create_file('f')
        f.write_data(self.large_data[:kb64-1], 0)
        self.assert_file_contents(self.large_data[:kb64-1])
        f.unlink()

        f = b.create_file('f')
        f.write_data(self.large_data[:kb64], 0)
        self.assert_file_contents(self.large_data[:kb64])
        f.unlink()

        f = b.create_file('f')
        f.write_data(self.large_data[:kb64+1], 0)
        self.assert_file_contents(self.large_data[:kb64+1])
        f.unlink()

        f = b.create_file('f')
        f.write_data('', kb64)
        self.assert_file_contents('\0' * kb64)
        f.unlink()

        f = b.create_file('f')
        f.write_data('', 3*kb64 + 500)
        self.assert_file_contents('\0' * (3 * kb64 + 500))
        f.unlink()

        f = b.create_file('f')
        f.write_data('x', kb64 - 1)
        self.assert_file_contents('\0' * (kb64 - 1) + 'x')
        f.unlink()

        f = b.create_file('f')
        f.write_data('x', kb64)
        self.assert_file_contents('\0' * (kb64) + 'x')
        f.unlink()

        f = b.create_file('f')
        f.write_data('_' * 10 * kb64, 0)
        f.write_data('', 3*kb64)
        self.assert_file_contents('_' * 10*kb64)
        f.unlink()

        f = b.create_file('f')
        f.write_data('_' * 10 * kb64, 0)
        f.write_data('', 3*kb64-1)
        self.assert_file_contents('_' * 10*kb64)
        f.unlink()

        f = b.create_file('f')
        f.write_data('_' * 10 * kb64, 0)
        f.write_data('', 3*kb64+1)
        self.assert_file_contents('_' * 10*kb64)
        f.unlink()

        f = b.create_file('f')
        f.write_data('_' * 10 * kb64, 0)
        f.write_data('x', 3*kb64 - 1)
        self.assert_file_contents('_' * (3*kb64-1) + 'x' + '_' * (7*kb64))
        f.unlink()

        f = b.create_file('f')
        f.write_data('_' * 10 * kb64, 0)
        f.write_data('x', 3*kb64)
        self.assert_file_contents('_' * (3*kb64) + 'x' + '_' * (7*kb64-1))
        f.unlink()

        f = b.create_file('f')
        f.write_data('_' * 10 * kb64, 0)
        f.write_data('x', 3*kb64+1)
        self.assert_file_contents('_' * (3*kb64+1) + 'x' + '_' * (7*kb64-2))
        f.unlink()

        f = b.create_file('f')
        f.write_data('_' * 10 * kb64, 0)
        f.write_data('xy', 3*kb64-1)
        self.assert_file_contents('_' * (3*kb64-1) + 'xy' + '_' * (7*kb64-1))
        f.unlink()

class InodeMetaTestCase(SpaghettiTestCase):
    def test_read(self):
        a = self.repo.get_root()['a.txt']
        self.assertEqual(a.inode['mode'], 0100644)
        self.assertEqual(a.inode['nlink'], 1)
        self.assertEqual(a.inode['uid'], 0)
        self.assertEqual(a.inode['gid'], 0)

    def test_write(self):
        a = self.repo.get_root()['a.txt']
        a.inode['mode'] = 0100755
        a.inode['uid'] = 1000

        repo2 = GitStorage(self.repo_path)
        a_2 = repo2.get_root()['a.txt']
        self.assertEqual(a_2.inode['mode'], 0100755)
        self.assertEqual(a_2.inode['uid'], 1000)

class GitStructureTestCase(SpaghettiTestCase):
    def test_commit_chain(self):
        def assert_head_ancestor(repo, ancestor_id):
            commit = repo.commit(repo.head())
            while True:
                try:
                    commit_id = commit.get_parents()[0]
                except IndexError:
                    self.fail('ancestor not in history of current head')

                if commit_id == ancestor_id:
                    return # we found the ancestor; test successful

                commit = repo.commit(commit_id)

        c = self.repo.get_root()['b']['c']
        HEAD_0 = dulwich.repo.Repo(self.repo_path).head()
        c.create_directory('x')

        repo = dulwich.repo.Repo(self.repo_path)
        HEAD_1 = repo.head()
        assert_head_ancestor(repo, HEAD_0)

        c['x'].create_file('f')
        repo = dulwich.repo.Repo(self.repo_path)
        assert_head_ancestor(repo, HEAD_1)

class RepoInitTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_path = path.join(self.tmpdir, 'test.sfs')

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_create_repo(self):
        repo = GitStorage.create(self.repo_path)

        git = dulwich.repo.Repo(self.repo_path)
        commit_tree = git.tree(git.commit(git.head()).tree)
        self.assertEqual(len(commit_tree.entries()), 4)

        inodes_tree = git.tree(commit_tree['inodes'][1])
        self.assertEqual(len(inodes_tree), 0)

        root_ls_blob = git.get_blob(commit_tree['root.ls'][1])
        self.assertEqual(root_ls_blob.data, '')

        root_sub_tree = git.tree(commit_tree['root.sub'][1])
        self.assertEqual(len(root_sub_tree.entries()), 0)

        features_blob = git.get_blob(commit_tree['features'][1])
        features_dict = json.loads(features_blob.data)
        self.assertEqual(features_dict['next_inode_number'], 1)

    def test_create_first_objects(self):
        repo = GitStorage.create(self.repo_path)
        root = repo.get_root()

        root.create_directory('some_folder')
        repo.commit('created "some folder"')
        repo2 = GitStorage(self.repo_path)
        self.assertEqual(set(repo2.get_root().keys()),
                         set(['some_folder']))
        self.assertEqual(set(repo2.get_root()['some_folder'].keys()), set())

        f = root.create_file('some_file')
        self.assertEqual(f.inode.name, 'i1')
        f.write_data('xy', 0)
        repo.commit('created "some file"')
        repo2 = GitStorage(self.repo_path)
        self.assertEqual(set(repo2.get_root().keys()),
                         set(['some_folder', 'some_file']))
        self.assertEqual(repo2.get_root()['some_file']._read_all_data(), 'xy')

class MockBlob(object):
    def __init__(self, data):
        self.data = data

class FeaturesTestCase(unittest.TestCase):
    def test_read(self):
        features = FeatureBlob(MockBlob('{"a": 13}'))
        self.assertEqual(features['a'], 13)
        self.assertEqual(features.get('a'), 13)
        self.assertRaises(KeyError, lambda: features['b'])
        self.assertRaises(KeyError, lambda: features.get('b'))
        self.assertEqual(features.get('b', 'x'), 'x')

    def test_write(self):
        mb = MockBlob('{"a": 13}')
        features = FeatureBlob(mb)
        features['b'] = 'asdf'
        self.assertEqual(json.loads(mb.data), {'a': 13, 'b': 'asdf'})

    def test_write_error(self):
        features = FeatureBlob(MockBlob('{"a": 13}'))

        def set_bad_key():
            features[13] = 'asdf'
        self.assertRaises(AssertionError, set_bad_key)

        def set_bad_value():
            features['b'] = ['asdf']
        self.assertRaises(AssertionError, set_bad_value)

        try:
            features['b'] = 'asdf'
            features['c'] = 15
        except ValueError:
            self.fail('Strings and numbers should be allowed')

if __name__ == '__main__':
    setup_logger('ERROR')
    unittest.main()
