import unittest
from support import GuitarTestCase


class ReadGitTestCase(GuitarTestCase):
    def test_walk(self):
        root = self.repo.get_root()
        self.assertTrue(root.is_dir)
        self.assertEqual(set(root.keys()), set(['a.txt', 'b']))
        self.assertRaises(KeyError, lambda: root['nonexistent'])

        a_txt = root['a.txt']
        self.assertFalse(a_txt.is_dir)
        self.assertEqual(a_txt.size, 14)
        self.assertEqual(a_txt.data, 'text file "a"\n')

        b = root['b']
        self.assertTrue(b.is_dir)
        self.assertEqual(set(b.keys()), set(['c', 'f.txt']))

        c = b['c']
        self.assertTrue(c.is_dir)
        self.assertEqual(set(c.keys()), set(['d.txt', 'e.txt']))

if __name__ == '__main__':
    unittest.main()
