import os
from os import path
from time import time

from spaghettifs.tests.support import randomdata
from spaghettifs.tests.test_filesystem import FuseMountTestCase

data_100_10KB = [randomdata(100*1024) for c in xrange(100)]

def write_small_files(test_path):
    for c, data in enumerate(data_100_10KB):
        write_file(path.join(test_path, str(c)), data)

def write_small_files_in_folders(test_path):
    for c in xrange(10):
        dname = path.join(test_path, str(c))
        os.mkdir(dname)
        for d in xrange(10):
            write_file(path.join(dname, str(d)), data_100_10KB[10*c + d])

def write_medium_files(test_path):
    for c in xrange(10):
        n = 10*c
        data = ''.join(data_100_10KB[n:n+10])
        write_file(path.join(test_path, str(c)), data)

def write_file(path, data):
    with open(path, 'wb') as f:
        f.write(data)

class BenchTestCase(FuseMountTestCase):
    def runTest(self, callback):
        self.setUp()
        test_path = path.join(self.mount_point, 'b')

        f0 = count_files(self.repo_path)
        t0 = time()
        callback(test_path)
        dt = time() - t0
        df = count_files(self.repo_path) - f0

        self.tearDown()

        return dt, df

def run_test(callback):
    test_env = BenchTestCase()

    tl = []
    for c in range(3):
        dt, df = test_env.runTest(callback)
        print '%.3f seconds, %d files' % (dt, df)
        tl.append(dt)
    print 'best: %.3f seconds' % min(tl)

def count_files(path):
    count = 0
    for root, dirs, files in os.walk(path):
        count += len(files)
    return count

def main():
    #run_test(write_small_files)
    #run_test(write_small_files_in_folders)
    run_test(write_medium_files)

if __name__ == '__main__':
    main()
