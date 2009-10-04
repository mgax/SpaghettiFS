import unittest
import os
from os import path
import sys
import subprocess
import time
from support import GitarTestCase


class FuseMountTestCase(GitarTestCase):
    def setUp(self):
        super(FuseMountTestCase, self).setUp()
        self.mount_point = path.join(self.tmpdir, 'mnt')
        os.mkdir(self.mount_point)
        script = ("from gitar.fs import mount; "
                  "mount(%s, %s)" % (repr(self.repo_path),
                                     repr(self.mount_point)))
        self.fsmount = subprocess.Popen([sys.executable, '-c', script],
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT)
        time.sleep(.3) # wait for mount operation to complete

    def tearDown(self):
        msg = subprocess.Popen(['umount', path.realpath(self.mount_point)],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT
                              ).communicate()[0]
        msg = self.fsmount.communicate()[0]
        #print msg

        print self.tmpdir
        super(FuseMountTestCase, self).tearDown()

    def test_listing(self):
        ls = os.listdir(self.mount_point)
        self.assertEqual(ls, ['a.txt'])

if __name__ == '__main__':
    unittest.main()
