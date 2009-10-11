from os import path
import unittest
from cStringIO import StringIO
import random
import struct

import dulwich

from support import SpaghettiTestCase, setup_logger
from spaghettifs.storage import GitStorage

def randomdata(size):
    f = StringIO()
    for c in xrange(size / 8 + 1):
        f.write(struct.pack('Q', random.getrandbits(64)))
    return f.getvalue()[:size]

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
        self.assertEqual(a_txt.data, 'text file "a"\n')
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
        self.assertEqual(g_txt.data, '')
        self.assertEqual(g_txt.name, 'g.txt')

        repo2 = GitStorage(self.repo_path)
        g_txt_2 = repo2.get_root()['b']['g.txt']
        self.assertFalse(g_txt_2.is_dir)
        self.assertEqual(g_txt_2.size, 0)
        self.assertEqual(g_txt_2.data, '')
        self.assertEqual(g_txt_2.name, 'g.txt')

    def test_write_file_data(self):
        def assert_git_contents(data):
            repo2 = GitStorage(self.repo_path)
            h_txt_2 = repo2.get_root()['b']['h.txt']
            self.assertEqual(h_txt_2.size, len(data))
            self.assertEqual(h_txt_2.data, data)

        b = self.repo.get_root()['b']
        h_txt = b.create_file('h.txt')
        h_txt.write_data('hello git!', 0)
        self.assertEqual(h_txt.size, 10)
        self.assertEqual(h_txt.data, 'hello git!')
        assert_git_contents('hello git!')

        h_txt.write_data(':)', 13)
        self.assertEqual(h_txt.size, 15)
        self.assertEqual(h_txt.data, 'hello git!\0\0\0:)')
        assert_git_contents('hello git!\0\0\0:)')

        h_txt.truncate(17)
        self.assertEqual(h_txt.size, 17)
        self.assertEqual(h_txt.data, 'hello git!\0\0\0:)\0\0')
        assert_git_contents('hello git!\0\0\0:)\0\0')

        h_txt.truncate(5)
        self.assertEqual(h_txt.size, 5)
        self.assertEqual(h_txt.data, 'hello')
        assert_git_contents('hello')

        h_txt.write_data('-there', 5)
        self.assertEqual(h_txt.size, 11)
        self.assertEqual(h_txt.data, 'hello-there')
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
        self.assertEqual(y.data, 'ydata')

        repo3 = GitStorage(self.repo_path)
        c_3 = repo3.get_root()['b']['c']
        self.assertEqual(set(c_3.keys()), set(['d.txt', 'e.txt', 'x']))
        x_3 = c_3['x']
        self.assertEqual(set(x_3.keys()), set(['y']))
        y_3 = x_3['y']
        self.assertEqual(y_3.data, 'ydata')

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
            self.assertEqual(f2.data, 'file contents %d' % c)

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
            self.assertEqual(g[name].data, repr(name*2))
            g[name].unlink()
            self.assertEqual(set(h[name].keys()), set(['afile', 'adir']))
            h[name]['afile'].unlink()
            h[name]['adir'].unlink()
            self.assertEqual(list(h[name].keys()), [])
            h[name].unlink()

        self.assertEqual(list(h.keys()), [])

class LargeFileTestCase(SpaghettiTestCase):
    large_data = randomdata(1024 * 1024) # 1 MB

    def assert_file_contents(self, reference):
        repo2 = GitStorage(self.repo_path)
        f = repo2.get_root()['b']['f']
        self.assertEqual(f.data, reference,
                         '`f.data` and `reference` do not match')

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
        f.write_data(self.large_data[:477*1024], 0)
        f.truncate(400*1024)
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

if __name__ == '__main__':
    unittest.main()
