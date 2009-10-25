import unittest
import os
from os import path
import sys
import subprocess
import time

from support import SpaghettiTestCase, randomdata
from spaghettifs.filesystem import LogWrap

if sys.platform == 'darwin':
    umount_cmd = ['umount']
elif sys.platform == 'linux2':
    umount_cmd = ['fusermount', '-u', '-z']
else:
    raise ValueError("Don't know how to unmount a fuse filesystem")

class FuseMountTestCase(SpaghettiTestCase):
    script_tmpl = "from spaghettifs.filesystem import mount; mount(%s, %s)"

    def setUp(self):
        super(FuseMountTestCase, self).setUp()
        self.mount_point = path.join(self.tmpdir, 'mnt')
        os.mkdir(self.mount_point)
        script = self.script_tmpl % (repr(self.repo_path),
                                     repr(self.mount_point))
        self.fsmount = subprocess.Popen([sys.executable, '-c', script],
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT)
        # wait for mount operation to complete
        for c in xrange(20):
            if path.ismount(self.mount_point):
                break
            time.sleep(.1)
        else:
            raise AssertionError('Filesystem did not mount after 2 seconds')

    def tearDown(self):
        msg = subprocess.Popen(umount_cmd + [path.realpath(self.mount_point)],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT
                              ).communicate()[0]
        self._output = self.fsmount.communicate()[0]
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
        self.assertEqual(os.stat(new_file_path).st_size, 0)
        self.assertEqual(open(new_file_path).read(), '')

        f.write('something here!')
        f.flush()
        self.assertEqual(os.stat(new_file_path).st_size, 15)
        self.assertEqual(open(new_file_path).read(), 'something here!')

        f.seek(10)
        f.write('there!')
        f.flush()
        self.assertEqual(os.stat(new_file_path).st_size, 16)
        self.assertEqual(open(new_file_path).read(), 'something there!')

        f.truncate(9)
        f.flush()
        self.assertEqual(os.stat(new_file_path).st_size, 9)
        self.assertEqual(open(new_file_path).read(), 'something')

        f.seek(15)
        f.write('else')
        f.flush()
        self.assertEqual(os.stat(new_file_path).st_size, 19)
        self.assertEqual(open(new_file_path).read(), 'something\0\0\0\0\0\0else')

    def test_large_data(self):
        _64K = 64*1024
        _1M = 1024*1024
        test_file_path = path.join(self.mount_point, 'newfile2')
        test_data = randomdata(_1M)
        f = open(test_file_path, 'wb')
        for c in xrange(0, _1M, _64K):
            f.write(test_data[c:c+_64K])
        f.close()

        f2 = open(test_file_path, 'rb')
        for c in xrange(0, _1M, _64K):
            d = f2.read(_64K)
            self.assertEqual(d, test_data[c:c+_64K])
        f2.close()

    def test_unlink(self):
        new_file_path = path.join(self.mount_point, 'newfile')
        f = open(new_file_path, 'wb')
        f.write('hey')
        f.close()
        self.assertTrue('newfile' in os.listdir(self.mount_point))
        os.unlink(new_file_path)
        self.assertFalse('newfile' in os.listdir(self.mount_point))

    def test_mkdir_listdir_rmdir(self):
        new_dir_path = path.join(self.mount_point, 'newdir')
        self.assertFalse('newdir' in os.listdir(self.mount_point))

        os.mkdir(new_dir_path)
        self.assertTrue('newdir' in os.listdir(self.mount_point))
        self.assertEqual(os.listdir(new_dir_path), [])

        os.rmdir(new_dir_path)
        self.assertFalse('newdir' in os.listdir(self.mount_point))

class FilesystemLoggingTestCase(unittest.TestCase):
    def test_custom_repr(self):
        self.assertEqual(repr(LogWrap('asdf')), repr('asdf'))
        self.assertEqual(repr(LogWrap('"')), repr('"'))
        self.assertEqual(repr(LogWrap('\'')), repr('\''))
        self.assertEqual(repr(LogWrap(u'q')), repr(u'q'))
        self.assertEqual(repr(LogWrap('qwer'*64)),  "'qwerqwerqw[...(len=256)]'")
        self.assertEqual(repr(LogWrap(u'asdf'*64)), "u'asdfasdfa[...(len=256)]'")
        self.assertEqual(repr(LogWrap(range(3))), '[0, 1, 2]')
        self.assertEqual(repr(LogWrap(range(100))), repr(range(100)))

if __name__ == '__main__':
    unittest.main()
