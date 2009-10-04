import unittest
from support import GitarTestCase


class ReadGitTestCase(GitarTestCase):
    def test_get_file(self):
        a = self.repo.get_file('/a.txt')
        self.assertEqual(a.name, 'a.txt')
        self.assertEqual(a.data, 'text file "a"\n')

    def test_list_files(self):
        ls = self.repo.list_files('/')
        self.assertEqual(ls, ['a.txt'])

if __name__ == '__main__':
    unittest.main()
