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
        self.assertRaises(ValueError, self.tt.new_blob, '')
        self.assertRaises(ValueError, self.tt.new_blob, 1234)
        try:
            self.tt.new_blob('12')
            self.tt.new_blob('asdf')
        except ValueError:
            self.fail('Should not raise exception')

    def test_create_retrieve_blobs(self):
        for name in ['345', '7', '22', '549', '0']:
            self.assertTrue(name not in self.tt)
            self.tt.new_blob(name).data = 'asdf'
            self.commit()
            self.assertTrue(name in self.tt)
            self.assertEqual(self.tt[name].data, 'asdf')
            self.assertTrue(name not in self.eg.root['tt'])

    def test_create_retrieve_trees(self):
        for name in ['24', '9', '873', '22']:
            self.assertTrue(name not in self.tt)
            self.tt.new_tree(name).new_blob('c').data = 'qwer'
            self.commit()
            self.assertTrue(name in self.tt)
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

    def test_clone(self):
        blobby = self.eg.root.new_blob('blobby')
        blobby.data = 'blobby data'
        self.tt.clone(blobby, '1234')
        blobby.data = 'qwer'
        self.assertEqual(self.tt['1234'].data, 'blobby data')
        self.assertEqual(self.eg.root['tt']['tt4']['1']['2']['3']['4'].data,
                         'blobby data')

    def test_remove(self):
        raw_tt = self.eg.root['tt']
        for name in ['345', '7', '22', '549']:
            self.tt.new_blob(name).data = 'asdf'

        self.assertTrue('345' in self.tt)
        self.assertTrue('tt3' in raw_tt)
        self.assertTrue('3' in raw_tt['tt3'])
        del self.tt['345']
        self.assertTrue('345' not in self.tt)
        self.assertTrue('tt3' in raw_tt)
        self.assertTrue('3' not in raw_tt['tt3'])

        self.assertTrue('7' in self.tt)
        self.assertTrue('tt1' in raw_tt)
        del self.tt['7']
        self.assertTrue('7' not in self.tt)
        self.assertTrue('tt1' not in raw_tt)

        self.assertRaises(KeyError, lambda: self.tt['345'])
        self.assertRaises(KeyError, lambda: self.tt['7'])
        self.assertEqual(self.tt['22'].data, 'asdf')
        self.assertEqual(self.tt['549'].data, 'asdf')

if __name__ == '__main__':
    setup_logger('ERROR')
    unittest.main()
