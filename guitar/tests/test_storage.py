import unittest
from support import GuitarTestCase


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

        from guitar.storage import Repo
        repo2 = Repo(self.repo_path)
        g_txt_2 = repo2.get_root()['b']['g.txt']
        self.assertFalse(g_txt_2.is_dir)
        self.assertEqual(g_txt_2.size, 0)
        self.assertEqual(g_txt_2.data, '')
        self.assertEqual(g_txt_2.name, 'g.txt')

if __name__ == '__main__':
    unittest.main()
