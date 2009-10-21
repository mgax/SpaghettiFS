from os import path
import unittest
import random
from StringIO import StringIO

import dulwich

from support import SpaghettiTestCase, setup_logger
from spaghettifs.easygit import EasyGit
from spaghettifs.storage import fsck

class FsckTestCase(SpaghettiTestCase):
    def setUp(self):
        super(FsckTestCase, self).setUp()
        del self.repo
        self.eg = EasyGit.open_repo(self.repo_path)

    def _fsck(self):
        out = StringIO()
        report = fsck(self.repo_path, out)
        return out.getvalue()

    def test_ok(self):
        self.assertEqual(self._fsck(), 'done; all ok\n')

    def test_missing_inodes(self):
        del self.eg.root['inodes']['i2']
        self.eg.commit('evil guy', 'removed inode i2')

        self.assertEqual(self._fsck(), "missing inode 'i2'\ndone; 1 errors\n")

if __name__ == '__main__':
    setup_logger('ERROR')
    unittest.main()
