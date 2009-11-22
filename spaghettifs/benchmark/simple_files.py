from os import path

from spaghettifs.benchmark import bench

def tiny_files_1k(mount_path):
    """ 1000 tiny files """
    for c in xrange(1000):
        with open(path.join(mount_path, 'file-%d' % c), 'w') as f:
            f.write('asdf')

def large_files_10(mount_path):
    """ 10 files of 10MB each """
    for c in xrange(10):
        with open(path.join(mount_path, 'file-%d' % c), 'w') as f:
            for d in xrange(1024):
                f.write('my 10-byte' * 1024)

def main():
    bench.log_to_stderr()
    for f in (tiny_files_1k, large_files_10):
        for c in range(3):
            with bench.TempFS() as temp_fs:
                print '%s: %r' % (f.func_name, temp_fs.measure(f))

if __name__ == '__main__':
    main()
