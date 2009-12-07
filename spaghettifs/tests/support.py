import unittest
import tempfile
import shutil
import os
import logging
import random
import struct
from cStringIO import StringIO

from spaghettifs import storage
from spaghettifs import easygit
from spaghettifs import treetree

stderr_handler = logging.StreamHandler()
stderr_handler.setLevel(logging.ERROR)
logging.getLogger('spaghettifs').addHandler(stderr_handler)

class SpaghettiTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_path = os.path.join(self.tmpdir, 'repo.sfs')

        os.mkdir(self.repo_path)
        eg = easygit.EasyGit.new_repo(self.repo_path, bare=True)
        with eg.root as root:
            with root.new_tree('inodes') as inodes:
                inodes_tt = treetree.TreeTree(inodes, prefix='it')
                def make_file_inode(inode_name, contents):
                    with inodes_tt.new_tree(inode_name[1:]) as i1:
                        b0 = i1.new_tree('bt1').new_blob('0')
                        b0.data = contents
                        meta = i1.new_blob('meta')
                        meta.data = ('mode: 0100644\n'
                                     'nlink: 1\n'
                                     'uid: 0\n'
                                     'gid: 0\n'
                                     'size: %(size)d\n') % {
                                         'size': len(contents),
                                     }

                make_file_inode('i1', 'text file "a"\n')
                make_file_inode('i2', 'file D!\n')
                make_file_inode('i3', 'the E file\n')
                make_file_inode('i4', 'F is here\n')

            root.new_blob('features').data = '{}'
            features = storage.FeatureBlob(root['features'])
            features['next_inode_number'] = 5
            features['inode_index_format'] = 'treetree'
            features['inode_format'] = 'treetree'

            root.new_blob('root.ls').data = 'a.txt i1\nb /\n'
            with root.new_tree('root.sub') as root_sub:
                root_sub.new_blob('b.ls').data = 'c /\nf.txt i4\n'
                with root_sub.new_tree('b.sub') as b_sub:
                    b_sub.new_blob('c.ls').data = 'd.txt i2\ne.txt i3\n'

        eg.commit("Spaghetti User <noreply@grep.ro>",
                  'Created empty filesystem')

        self.repo = storage.GitStorage(self.repo_path)

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
