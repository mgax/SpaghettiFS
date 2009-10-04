from errno import ENOENT
from stat import S_IFDIR, S_IFREG
from time import time
from fuse import FUSE, Operations, LoggingMixIn
from persistence import Repo

class GuitarFs(LoggingMixIn, Operations):
    def __init__(self, repo):
        self.repo = repo

    def get_obj(self, path):
        #assert(path.startswith('/'))
        obj = self.repo.get_root()
        for frag in path[1:].split('/'):
            if frag == '':
                continue
            try:
                obj = obj[frag]
            except KeyError:
                return None

        return obj

    def getattr(self, path, fh=None):
        obj = self.get_obj(path)
        if obj is None:
            raise OSError(ENOENT, '')

        if obj.is_dir:
            st = dict(st_mode=(S_IFDIR | 0755), st_nlink=2)
        else:
            st = dict(st_mode=(S_IFREG | 0444), st_size=obj.size)

        st['st_ctime'] = st['st_mtime'] = st['st_atime'] = time()
        return st

    def read(self, path, size, offset, fh):
        obj = self.get_obj(path)
        if obj is None:
            return ''
        elif obj.is_dir:
            return ''
        else:
            return obj.data

    def readdir(self, path, fh):
        names = self.repo.get_root().keys()
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
    fs = GuitarFs(Repo(repo_path))
    return FUSE(fs, mount_path, foreground=True)
