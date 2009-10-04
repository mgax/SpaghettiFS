from errno import ENOENT
from stat import S_IFDIR, S_IFREG
from time import time
from fuse import FUSE, Operations, LoggingMixIn
from persistence import Repo

class GitarFs(LoggingMixIn, Operations):
    def __init__(self, repo):
        self.repo = repo

    def getattr(self, path, fh=None):
        if path == '/':
            st = dict(st_mode=(S_IFDIR | 0755), st_nlink=2)
        #elif path == 'x':
        #    st = dict(st_mode=(S_IFREG | 0444), st_size=1)
        else:
            raise OSError(ENOENT, '')

        st['st_ctime'] = st['st_mtime'] = st['st_atime'] = time()
        return st

    def read(self, path, size, offset, fh):
        #if path == 'x':
        #    return 'y'
        #else:
        #    return ''
        return ''

    def readdir(self, path, fh):
        names = self.repo.list_files(path)
        print names
        return ['.', '..'] + names

    access = None
    flush = None
    getxattr = None
    listxattr = None
    open = None
    opendir = None
    release = None
    releasedir = None
    statfs = None

def mount(repo_path, mount_path):
    fs = GitarFs(Repo(repo_path))
    return FUSE(fs, mount_path, foreground=True)
