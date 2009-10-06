import unittest
from support import GuitarTestCase
from guitar.storage import Repo


class BackendTestCase(GuitarTestCase):
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

        repo2 = Repo(self.repo_path)
        g_txt_2 = repo2.get_root()['b']['g.txt']
        self.assertFalse(g_txt_2.is_dir)
        self.assertEqual(g_txt_2.size, 0)
        self.assertEqual(g_txt_2.data, '')
        self.assertEqual(g_txt_2.name, 'g.txt')

    def test_write_file_data(self):
        def assert_git_contents(data):
            repo2 = Repo(self.repo_path)
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

        repo2 = Repo(self.repo_path)
        c_2 = repo2.get_root()['b']['c']
        self.assertEqual(set(c_2.keys()), set(['e.txt']))


if __name__ == '__main__':
    unittest.main()
