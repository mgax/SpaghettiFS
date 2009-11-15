import os
from errno import ENOENT
from stat import S_IFDIR, S_IFREG
from time import time
import logging
from datetime import datetime
import threading

from fuse import FUSE, Operations
from storage import GitStorage

log = logging.getLogger('spaghettifs.filesystem')
log.setLevel(logging.DEBUG)

WRITE_BUFFER_SIZE = 3 * 1024 * 1024 # 3MB

class SpaghettiFS(Operations):
    def __init__(self, repo):
        self.repo = repo
        self._write_count = 0
        # the FUSE library seems to assume we're thread-safe, so we use a
        # big fat lock, just in case
        self._lock = threading.Lock()

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
            st['st_nlink'] = obj.inode['nlink']

            # FUSE seeems to ignore our st_ino
            #st['st_ino'] = int(obj.inode.name[1:])

        st['st_ctime'] = st['st_mtime'] = st['st_atime'] = time()
        return st

    def create(self, path, mode):
        parent_path, file_name = os.path.split(path)
        parent = self.get_obj(parent_path)
        parent.create_file(file_name)
        return 0

    def link(self, target, source):
        source_obj = self.get_obj(source)
        target_parent_obj = self.get_obj(os.path.dirname(target))
        target_parent_obj.link_file(os.path.basename(target), source_obj)

    def mkdir(self, path, mode):
        parent_path, dir_name = os.path.split(path)
        parent = self.get_obj(parent_path)
        parent.create_directory(dir_name)

    def read(self, path, size, offset, fh):
        obj = self.get_obj(path)
        if obj is None or obj.is_dir:
            return ''
        else:
            return obj.read_data(offset, size)

    def readdir(self, path, fh):
        obj = self.get_obj(path)
        return ['.', '..'] + list(obj.keys())

    def rmdir(self, path):
        obj = self.get_obj(path)
        if obj is None or not obj.is_dir:
            return

        obj.unlink()

    def truncate(self, path, length, fh=None):
        obj = self.get_obj(path)
        if obj is None or obj.is_dir:
            return

        obj.truncate(length)

    def unlink(self, path):
        obj = self.get_obj(path)
        if obj is None or obj.is_dir:
            return

        obj.unlink()

    def write(self, path, data, offset, fh):
        obj = self.get_obj(path)
        if obj is None or obj.is_dir:
            return 0

        obj.write_data(data, offset)

        if not self.repo.autocommit:
            self._write_count += len(data)
            if self._write_count > WRITE_BUFFER_SIZE:
                self.repo.commit(amend=True, branch="mounted")
                self._write_count = 0

        return len(data)

#    access = None
    flush = None
    getxattr = None
    listxattr = None
    open = None
    opendir = None
    release = None
    releasedir = None
    statfs = None

    def __call__(self, op, path, *args):
        log.debug('FUSE api call: %r %r %r',
                  op, path, tuple(LogWrap(arg) for arg in args))
        ret = '[Unknown Error]'
        self._lock.acquire()
        try:
            ret = super(SpaghettiFS, self).__call__(op, path, *args)
            return ret
        except OSError, e:
            ret = str(e)
            raise
        finally:
            self._lock.release()
            log.debug('FUSE api return: %r %r', op, LogWrap(ret))

class LogWrap(object):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        if isinstance(self.value, basestring) and len(self.value) > 20:
            r = repr(self.value[:12])
            return '%s[...(len=%d)]%s' % (r[:11], len(self.value), r[-1])
        else:
            return repr(self.value)

    def __str__(self):
        return repr(self)

datefmt = lambda dt: dt.strftime('%Y-%m-%d %H:%M:%S')

class _open_fs(object):
    def __init__(self, repo_path, cls):
        self.repo_path = repo_path
        self.cls = cls

    def __enter__(self):
        self.time_mount = datetime.now()
        self.repo = GitStorage(self.repo_path, autocommit=False)
        msg = ("[temporary commit; currently mounted, since %s]" %
               datefmt(self.time_mount))
        self.repo.commit(msg,
                         branch="mounted",
                         head_id=self.repo.eg.get_head_id('master'))
        return self.cls(self.repo)

    def __exit__(self, e0, e1, e2):
        self.time_unmount = datetime.now()
        msg = ("Mounted operations:\n  mounted at %s\n  unmounted at %s\n" %
               (datefmt(self.time_mount), datefmt(self.time_unmount)))
        self.repo.commit(msg)
        del self.repo.eg.git.refs['refs/heads/mounted']

def mount(repo_path, mount_path, cls=SpaghettiFS, loglevel=logging.ERROR):
    if loglevel is not None:
        stderr_handler = logging.StreamHandler()
        stderr_handler.setLevel(loglevel)
        logging.getLogger('spaghettifs').addHandler(stderr_handler)

    with _open_fs(repo_path, cls) as fs:
        FUSE(fs, mount_path, foreground=True)
