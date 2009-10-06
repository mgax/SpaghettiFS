import unittest
import os
from os import path
import sys
import subprocess
import time
from support import GuitarTestCase


class FuseMountTestCase(GuitarTestCase):
    def setUp(self):
        super(FuseMountTestCase, self).setUp()
        self.mount_point = path.join(self.tmpdir, 'mnt')
        os.mkdir(self.mount_point)
        script = ("from guitar.fs import mount; "
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
        super(FuseMountTestCase, self).tearDown()

    def test_listing(self):
        ls = os.listdir(self.mount_point)
        self.assertEqual(set(ls), set(['a.txt', 'b']))

    def test_read_file(self):
        data = open(path.join(self.mount_point, 'a.txt')).read()
        self.assertEqual(data, 'text file "a"\n')

    def test_write_file(self):
        new_file_path = path.join(self.mount_point, 'newfile')
        self.assertFalse('newfile' in os.listdir(self.mount_point))

        f = open(new_file_path, 'wb')
        self.assertTrue('newfile' in os.listdir(self.mount_point))
        self.assertEqual(open(new_file_path).read(), '')

        f.write('something here!')
        f.flush()
        self.assertEqual(open(new_file_path).read(), 'something here!')

        f.seek(10)
        f.write('there!')
        f.flush()
        self.assertEqual(open(new_file_path).read(), 'something there!')

        f.truncate(9)
        f.flush()
        self.assertEqual(open(new_file_path).read(), 'something')

        f.seek(15)
        f.write('else')
        f.flush()
        self.assertEqual(open(new_file_path).read(), 'something\0\0\0\0\0\0else')

        f.close()

if __name__ == '__main__':
    unittest.main()
