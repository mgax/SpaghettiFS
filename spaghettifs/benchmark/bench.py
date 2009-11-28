import multiprocessing
import tempfile
import os
from os import path
import shutil
import logging
import time
import collections

from spaghettifs import storage
from spaghettifs import filesystem
from spaghettifs.tests import test_filesystem
import Queue

log = logging.getLogger('spaghettifs.bench')
log.setLevel(logging.DEBUG)

class LogWatcher(object):
    level = logging.DEBUG
    def __init__(self):
        logging.getLogger('spaghettifs').addHandler(self)
        self.stats = collections.defaultdict(int)

    def handle(self, record):
        self.stats['log_count'] += 1
        if 'loading git tree' in record.msg:
            self.stats['tree_loads'] += 1
        elif 'loading git blob' in record.msg:
            self.stats['blob_loads'] += 1
        elif 'Loaded inode' in record.msg:
            self.stats['inode_loads'] += 1

    def report(self):
        return self.stats

def fs_mount(repo_path, mount_path, stats_queue):
    log_watcher = LogWatcher()
    time0 = time.time()
    clock0 = time.clock()
    filesystem.mount(repo_path, mount_path)
    stats = {'time': time.time() - time0,
             'clock': time.clock() - clock0}
    stats.update(log_watcher.report())
    stats_queue.put(stats)

class TempFS(object):
    def __enter__(self):
        self.temp_path = tempfile.mkdtemp()
        log.debug('setting up temporary filesystem at %r', self.temp_path)

        self.mount_path = path.join(self.temp_path, 'mnt')
        os.mkdir(self.mount_path)

        self.repo_path = path.join(self.temp_path, 'repo.sfs')
        storage.GitStorage.create(self.repo_path)

        return self

    def __exit__(self, *args):
        log.debug('cleaning up temporary filesystem at %r', self.temp_path)
        shutil.rmtree(self.temp_path)

    def measure(self, do_work):
        return measure(do_work, self.repo_path, self.mount_path)

def measure(do_work, repo_path, mount_path):
    stats_queue = multiprocessing.Queue()
    log.debug('starting mounter process; repo_path=%r, mount_path=%r',
              mount_path, repo_path)
    args = (repo_path, mount_path, stats_queue)
    p = multiprocessing.Process(target=fs_mount, args=args)
    p.start()
    if test_filesystem.wait_for_mount(mount_path):
        log.debug('mount successful')
    else:
        log.error('mount failed')
        return

    try:
        do_work(mount_path)
    except:
        log.debug('caught exception; doing cleanup and re-raising')
        raise
    finally:
        log.debug('running unmount command')
        test_filesystem.do_umount(mount_path)
        log.debug('waiting for mounter stats, timeout=2')
        try:
            stats = stats_queue.get(timeout=2)
        except Queue.Empty:
            log.error('timeout while waiting for stats')
            stats = None
        log.debug('received stats: %r', stats)
        log.debug('joining mounter process, timeout=2')
        p.join(timeout=2)
        if p.is_alive():
            log.error('joining child process failed')
        else:
            log.debug('join successful')

    return stats

def log_to_stderr(debug=False):
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG if debug else logging.INFO)
    log.addHandler(handler)

if __name__ == '__main__':
    def blanktest(mount_path):
        print 'performing blank test at', mount_path

    log_to_stderr(debug=True)
    with TempFS() as tfs:
        print tfs.measure(blanktest)
