import unittest
import tempfile
import shutil
import os
import logging
import random
import struct
from cStringIO import StringIO

from spaghettifs.storage import GitStorage
from spaghettifs.easygit import EasyGit

stderr_handler = logging.StreamHandler()
stderr_handler.setLevel(logging.ERROR)
logging.getLogger('spaghettifs').addHandler(stderr_handler)

class SpaghettiTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_path = os.path.join(self.tmpdir, 'repo.sfs')

        os.mkdir(self.repo_path)
        eg = EasyGit.new_repo(self.repo_path, bare=True)
        with eg.root as root:
            with root.new_tree('inodes') as inodes:
                inodes.new_tree('i1').new_blob('b0').data = 'text file "a"\n'
                inodes.new_tree('i2').new_blob('b0').data = 'file D!\n'
                inodes.new_tree('i3').new_blob('b0').data = 'the E file\n'
                inodes.new_tree('i4').new_blob('b0').data = 'F is here\n'
            root.new_blob('root.ls').data = 'a.txt i1\nb /\n'
            with root.new_tree('root.sub') as root_sub:
                root_sub.new_blob('b.ls').data = 'c /\nf.txt i4\n'
                with root_sub.new_tree('b.sub') as b_sub:
                    b_sub.new_blob('c.ls').data = 'd.txt i2\ne.txt i3\n'

        eg.commit("Spaghetti User <noreply@grep.ro>",
                  'Created empty filesystem')

        self.repo = GitStorage(self.repo_path)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

def randomdata(size):
    f = StringIO()
    for c in xrange(size / 8 + 1):
        f.write(struct.pack('Q', random.getrandbits(64)))
    return f.getvalue()[:size]

def setup_logger(log_level):
    import logging
    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(getattr(logging, log_level))
    logging.getLogger('spaghettifs').addHandler(stderr_handler)
