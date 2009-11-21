import unittest
import tempfile
import shutil

import dulwich
from support import setup_logger
from spaghettifs.easygit import EasyGit, EasyTree, EasyBlob
from spaghettifs.treetree import TreeTree

class BasicTestCase(unittest.TestCase):
    def setUp(self):
        self.repo_path = tempfile.mkdtemp()
        self.eg = EasyGit.new_repo(self.repo_path, bare=True)
        self.tt = TreeTree(self.eg.root.new_tree('tt'))

    def tearDown(self):
        shutil.rmtree(self.repo_path)

    def commit(self):
        self.eg.commit(author="Spaghetti User <noreply@grep.ro>",
                       message="test commit")

    def test_valid_ids(self):
        self.assertRaises(ValueError, self.tt.new_tree, 'asdf')
        self.assertRaises(ValueError, self.tt.new_blob, 'asdf')
        self.assertRaises(ValueError, self.tt.new_blob, '')
        self.assertRaises(ValueError, self.tt.new_blob, '-')
        try:
            self.tt.new_blob('12')
        except ValueError:
            self.fail('Should not raise exception')

    def test_create_retrieve_blobs(self):
        for name in ['345', '7', '22', '549', '0']:
            self.tt.new_blob(name).data = 'asdf'
            self.commit()
            self.assertEqual(self.tt[name].data, 'asdf')
            self.assertTrue(name not in self.eg.root['tt'])

    def test_create_retrieve_trees(self):
        for name in ['24', '9', '873', '22']:
            self.tt.new_tree(name).new_blob('c').data = 'qwer'
            self.commit()
            self.assertEqual(self.tt[name]['c'].data, 'qwer')
            self.assertTrue(name not in self.eg.root['tt'])

    def test_structure(self):
        raw_tt = self.eg.root['tt']
        self.tt.new_tree('123')
        self.assertTrue(isinstance(raw_tt['tt3']['1']['2']['3'], EasyTree))
        self.tt.new_blob('22')
        self.assertTrue(isinstance(raw_tt['tt2']['2']['2'], EasyBlob))
        self.assertRaises(KeyError, lambda: self.tt['33'])

    def test_overwrite(self):
        self.tt.new_tree('123')
        self.assertRaises(ValueError, self.tt.new_blob, '123')

if __name__ == '__main__':
    setup_logger('ERROR')
    unittest.main()