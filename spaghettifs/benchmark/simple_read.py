from os import path
from pprint import pprint

from probity import checksum
checksum.BLOCK_SIZE = 65536
from spaghettifs.benchmark import bench

class FileReader(object):
    """ read the files in the given directory """

    def __init__(self, subdir=''):
        self.subdir = subdir

    def __call__(self, mount_path):
        folder_path = path.join(mount_path, self.subdir)
        print checksum.folder_sha1(folder_path, lambda d: None)

def main(repo_path, mount_path, subdir):
    bench.log_to_stderr()
    file_reader = FileReader(subdir)
    for c in range(1):
        stats = bench.measure(file_reader, repo_path, mount_path)
        pprint(stats)

if __name__ == '__main__':
    import sys
    main(*sys.argv[1:])
