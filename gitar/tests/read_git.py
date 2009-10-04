import unittest
from support import GitarTestCase


class ReadGitTestCase(GitarTestCase):
    def test_walk(self):
        root = self.repo.get_root()
        self.assertEqual(root.is_dir, True)
        self.assertEqual(root.keys(), ['a.txt'])
        self.assertRaises(KeyError, lambda: root['nonexistent'])
        a_txt = root['a.txt']
        self.assertEqual(a_txt.is_dir, False)
        self.assertEqual(a_txt.size, 14)
        self.assertEqual(a_txt.data, 'text file "a"\n')

if __name__ == '__main__':
    unittest.main()
