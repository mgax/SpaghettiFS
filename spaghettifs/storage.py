import os
from time import time
import UserDict
import logging
import binascii
from cStringIO import StringIO
from itertools import chain
import weakref
import json
import functools

from easygit import EasyGit
from treetree import TreeTree

log = logging.getLogger('spaghettifs.storage')
log.setLevel(logging.DEBUG)

class FeatureBlob(object):
    def __init__(self, blob):
        self.blob = blob

    def load(self):
        return json.loads(self.blob.data)

    def save(self, data):
        self.blob.data = json.dumps(data)

    nothing = object() # marker object
    def get(self, key, default=nothing):
        try:
            return self.load()[key]
        except KeyError:
            if default is not self.nothing:
                return default
            else:
                raise

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        assert isinstance(key, basestring)
        assert isinstance(value, (basestring, int))
        data = self.load()
        data[key] = value
        self.save(data)

class GitStorage(object):
    commit_author = "Spaghetti User <noreply@grep.ro>"

    @classmethod
    def create(cls, repo_path):
        if not os.path.isdir(repo_path):
            os.mkdir(repo_path)

        eg = EasyGit.new_repo(repo_path, bare=True)

        inodes = eg.root.new_tree('inodes')
        root_ls = eg.root.new_blob('root.ls')
        root_sub = eg.root.new_tree('root.sub')
        features_blob = eg.root.new_blob('features')

        features_blob.data = '{}'
        features = FeatureBlob(features_blob)
        features['next_inode_number'] = 1
        features['inode_index_format'] = 'treetree'
        features['inode_format'] = 'treetree'

        eg.commit(cls.commit_author, 'Created empty filesystem')

        return cls(repo_path)

    def __init__(self, repo_path, autocommit=True):
        self.eg = EasyGit.open_repo(repo_path)
        features = FeatureBlob(self.eg.root['features'])
        assert features.get('inode_format', None) == 'treetree'
        assert features.get('inode_index_format', None) == 'treetree'
        self.autocommit = autocommit
        log.debug('Loaded storage, autocommit=%r, HEAD=%r',
                  autocommit, self.eg.get_head_id())
        self._inode_cache = {}
        self._inodes_tt = TreeTree(self.eg.root['inodes'], prefix='it')

    def get_root(self):
        commit_tree = self.eg.root
        root_ls = commit_tree['root.ls']
        root_sub = commit_tree['root.sub']
        root = StorageDir('root', root_ls, root_sub, '/', self, None)
        root.path = '/'
        return root

    def get_inode(self, name):
        if name in self._inode_cache:
            inode = self._inode_cache[name]()
            if inode is None:
                del self._inode_cache[name]
            else:
                return inode

        inode_tree = self._inodes_tt[name[1:]]
        inode = StorageInode(name, inode_tree, self)
        self._inode_cache[name] = weakref.ref(inode)

        return inode

    def create_inode(self):
        features = FeatureBlob(self.eg.root['features'])
        next_inode_number = features['next_inode_number']
        features['next_inode_number'] = next_inode_number + 1

        inode_name = 'i%d' % next_inode_number
        inode_tree = self._inodes_tt.new_tree(inode_name[1:])
        inode_tree.new_blob('meta').data = StorageInode.default_meta
        return self.get_inode(inode_name)

    def _remove_inode(self, name):
        if name in self._inode_cache:
            del self._inode_cache[name]

    def _autocommit(self):
        if self.autocommit:
            self.commit("Auto commit")

    def commit(self, message=None, amend=False, head_id=None, branch='master'):
        log.info('Committing')

        if head_id is None:
            head_id = self.eg.get_head_id(branch)

        if amend:
            git = self.eg.git
            prev_commit = git.commit(head_id)
            parents = prev_commit.parents
            if message is None:
                message = prev_commit.message
        else:
            parents = [head_id]

        assert message is not None

        self.eg.commit(self.commit_author, message, parents,
                       branch=branch)

class StorageDir(object, UserDict.DictMixin):
    is_dir = True

    def __init__(self, name, ls_blob, sub_tree, path, storage, parent):
        self.name = name
        self.ls_blob = ls_blob # blob that lists our contents
        self.sub_tree = sub_tree # tree that keeps our subfolders
        self.path = path
        self.storage = storage
        self.parent = parent
        log.debug('Loaded folder %r', name)

    def _iter_contents(self):
        return iter_entries(self.ls_blob.data)

    def keys(self):
        for name, value in self._iter_contents():
            yield name

    def __getitem__(self, key):
        for name, value in self._iter_contents():
            if key == name:
                break
        else:
            raise KeyError('Folder entry %s not found' % repr(key))

        if value == '/':
            qname = quote(name)
            child_ls = self.sub_tree[qname + '.ls']
            try:
                child_sub = self.sub_tree[qname + '.sub']
            except KeyError:
                child_sub = self.sub_tree.new_tree(qname + '.sub')
                self.storage._autocommit()
            return StorageDir(name, child_ls, child_sub,
                              self.path + name + '/',
                              self.storage, self)
        else:
            inode = self.storage.get_inode(value)
            return StorageFile(name, inode, self)

    def create_file(self, name, inode=None):
        check_filename(name)

        if inode is None:
            log.info('Creating file %r in %r', name, self.path)
            inode = self.storage.create_inode()
        else:
            assert(inode.storage is self.storage)
            log.info('Linking file %r in %r to inode %r',
                     name, self.path, inode.name)
            inode['nlink'] += 1

        with self.ls_blob as b:
            b.data += "%s %s\n" % (quote(name), inode.name)

        self.storage._autocommit()

        return self[name]

    def link_file(self, name, src_file):
        """ Make a new file, hard-linked to `src_file` """
        assert not src_file.is_dir
        return self.create_file(name, src_file.inode)

    def create_directory(self, name):
        check_filename(name)
        log.info('Creating directory %s in %s', repr(name), repr(self.path))

        qname = quote(name)
        with self.sub_tree as st:
            child_ls_blob = st.new_blob(qname + '.ls')
        with self.ls_blob as b:
            b.data += "%s /\n" % qname

        self.storage._autocommit()

        return self[name]

    def remove_ls_entry(self, rm_name):
        ls_data = ''
        removed_count = 0
        for name, value in self._iter_contents():
            if name == rm_name:
                log.debug('Removing ls entry %s from %s',
                          repr(rm_name), repr(self.path))
                removed_count += 1
            else:
                ls_data += '%s %s\n' % (quote(name), value)
        assert removed_count == 1

        with self.ls_blob as b:
            b.data = ls_data

        self.storage._autocommit()

    def unlink(self):
        log.info('Removing folder %s', repr(self.path))

        self.ls_blob.remove()
        self.sub_tree.remove()
        self.parent.remove_ls_entry(self.name)

        self.storage._autocommit()

class StorageInode(object):
    blocksize = 64*1024 # 64 KB
    #blocksize = 1024*1024 # 1024 KB

    default_meta = ('mode: 0100644\n'
                    'nlink: 1\n'
                    'uid: 0\n'
                    'gid: 0\n'
                    'size: 0\n')
    int_meta = ('nlink', 'uid', 'gid', 'size')
    oct_meta = ('mode',)

    def __init__(self, name, tree, storage):
        self.name = name
        self.tree = tree
        self.storage = storage
        self.tt = TreeTree(tree, prefix='bt')
        log.debug('Loaded inode %r', name)

    def _read_meta(self):
        try:
            meta_blob = self.tree['meta']
        except KeyError:
            meta_raw = self.default_meta
        else:
            meta_raw = meta_blob.data

        return dict(line.split(': ', 1)
                    for line in meta_raw.strip().split('\n'))

    def _write_meta(self, meta_data):
        meta_raw = ''.join('%s: %s\n' % (key, value)
                           for key, value in sorted(meta_data.items()))
        self.tree.new_blob('meta').data = meta_raw
        self.storage._autocommit()

    def __getitem__(self, key):
        value = self._read_meta()[key]

        if key in self.oct_meta:
            value = int(value, base=8)
        elif key in self.int_meta:
            value = int(value)

        return value

    def __setitem__(self, key, value):
        if key in self.oct_meta:
            value = '0%o' % value
        elif key in self.int_meta:
            value = '%d' % value
        else:
            raise NotImplementedError

        meta_data = self._read_meta()
        meta_data[key] = value
        self._write_meta(meta_data)

    def read_block(self, n):
        block_name = str(n)
        log.debug('Reading block %r of inode %r', block_name, self.name)
        try:
            block = self.tt[block_name]
        except KeyError:
            return ''
        else:
            return block.data

    def write_block(self, n, data):
        block_name = str(n)
        log.debug('Writing block %r of inode %r', block_name, self.name)
        try:
            block = self.tt[block_name]
        except KeyError:
            block = self.tt.new_blob(block_name)
        block.data = data

        self.storage._autocommit()

    def delete_block(self, n):
        block_name = str(n)
        log.debug('Removing block %r of inode %r', block_name, self.name)
        del self.tt[block_name]

        self.storage._autocommit()

    def read_data(self, offset, length):
        end = offset + length
        eof = self['size']
        if end > eof:
            end = eof
            length = end - offset
            if length <= 0:
                return ''
        first_block = offset / self.blocksize
        last_block = end / self.blocksize

        output = StringIO()
        for n_block in range(first_block, last_block+1):
            block_offset = n_block * self.blocksize

            fragment_offset = 0
            if n_block == first_block:
                fragment_offset = offset - block_offset

            fragment_end = self.blocksize
            if n_block == last_block:
                fragment_end = end - block_offset

            block_data = self.read_block(n_block)
            fragment = block_data[fragment_offset:fragment_end]
            assert len(fragment) == fragment_end - fragment_offset
            output.write(fragment)

        output = output.getvalue()
        assert len(output) == length
        return output

    def write_data(self, data, offset):
        current_size = self['size']
        if current_size < offset:
            self.truncate(offset)

        log.info('Inode %s writing %d bytes at offset %d',
                 repr(self.name), len(data), offset)

        end = offset + len(data)
        first_block = offset / self.blocksize
        last_block = end / self.blocksize

        for n_block in range(first_block, last_block+1):
            block_offset = n_block * self.blocksize

            insert_offset = 0
            if n_block == first_block:
                insert_offset = offset - block_offset

            insert_end = self.blocksize
            if n_block == last_block:
                insert_end = end - block_offset

            data_start = block_offset + insert_offset - offset
            data_end = block_offset + insert_end - offset

            log.debug('Updating inode %d between (%d, %d) '
                      'with data slice between (%d, %d)',
                      n_block, insert_offset, insert_end,
                      data_start, data_end)

            current_data = self.read_block(n_block)
            datafile = StringIO()
            datafile.write(current_data)
            datafile.seek(insert_offset)
            datafile.write(data[data_start:data_end])
            self.write_block(n_block, datafile.getvalue())

        if end > current_size:
            self['size'] = end

    def truncate(self, new_size):
        log.info("Truncating inode %s, new size %d", repr(self.name), new_size)

        current_size = self['size']
        if current_size < new_size:
            # TODO: avoid creating one big string
            self.write_data('\0' * (new_size - current_size), current_size)

        elif current_size > new_size:
            first_block = new_size / self.blocksize
            last_block = current_size / self.blocksize
            truncate_offset = new_size % self.blocksize

            for n_block in range(first_block, last_block+1):
                if n_block == first_block and truncate_offset > 0:
                    old_data = self.read_block(n_block)
                    self.write_block(n_block, old_data[:truncate_offset])
                else:
                    self.delete_block(n_block)

        self['size'] = new_size

    def unlink(self):
        log.info('Unlinking inode %r', self.name)

        nlink = self['nlink'] - 1
        if nlink > 0:
            log.info('Links remaining for inode %r: %d', self.name, nlink)
            self['nlink'] = nlink
        else:
            log.info('Links remaining for inode %r: 0; removing.', self.name)
            self.storage._remove_inode(self.name)
            self.tree.remove()

        self.storage._autocommit()

class StorageFile(object):
    is_dir = False

    def __init__(self, name, inode, parent):
        self.name = name
        self.inode = inode
        self.parent = parent

    @property
    def path(self):
        return self.parent.path + self.name

    @property
    def size(self):
        return self.inode['size']

    def _read_all_data(self):
        return self.read_data(0, self.size)

    def read_data(self, offset, length):
        return self.inode.read_data(offset, length)

    def write_data(self, data, offset):
        return self.inode.write_data(data, offset)

    def truncate(self, new_size):
        return self.inode.truncate(new_size)

    def unlink(self):
        log.info('Unlinking file %s', repr(self.path))
        self.parent.remove_ls_entry(self.name)
        self.inode.unlink()

def quote(name):
    return (binascii.b2a_qp(name, quotetabs=True, istext=False)
            .replace('=\n', ''))

unquote = binascii.a2b_qp

def check_filename(name):
    if name in ('.', '..', '') or '/' in name or len(name) > 255:
        raise ValueError("Bad filename %r" % name)

def iter_entries(ls_data):
    for line in ls_data.split('\n'):
        if not line:
            continue
        name, value = line.rsplit(' ', 1)
        yield unquote(name), value

upgrade_log = logging.getLogger('spaghettifs.storage.upgrade')
upgrade_log.setLevel(logging.DEBUG)

def storage_format_upgrade(upgrade_name, upgrade_from, upgrade_to):
    def decorator(the_upgrade):
        @functools.wraps(the_upgrade)
        def wrapper(repo_path):
            eg = EasyGit.open_repo(repo_path)

            if 'features' not in eg.root:
                upgrade_log.info('Creating "features" blob for repository %r',
                         repo_path)
                b = eg.root.new_blob('features')
                b.data = '{}'
            features = FeatureBlob(eg.root['features'])

            for name, value in upgrade_from.iteritems():
                if features.get(name, None) is not value:
                    upgrade_log.debug('Skipping upgrade %r on repository %r, '
                              'feature %r is not %r',
                              upgrade_name, repo_path, name, value)
                    return

            upgrade_log.info('Starting upgrade %r on repository %r',
                     upgrade_name, repo_path)
            the_upgrade(eg)

            upgrade_log.debug('Writing features for upgrade %r', upgrade_name)
            for name, value in upgrade_to.iteritems():
                features[name] = value

            message = "Update script %r" % upgrade_name
            eg.commit(GitStorage.commit_author, message,
                      [eg.get_head_id('master')])
            upgrade_log.info('Finished upgrade %r on repository %r',
                     upgrade_name, repo_path)

        return wrapper

    return decorator

@storage_format_upgrade('Convert inode blocks list to treetree',
                       upgrade_from={'inode_format': None},
                       upgrade_to={'inode_format': 'treetree'})
def convert_fs_to_treetree_inodes(eg):
    """
    Convert an existing filesystem from the "inode with flat list of blocks"
    format to the "inode with treetree of blocks" format.
    """

    inode_index = eg.root['inodes']

    class DummyStorage(object):
        def _autocommit(self): pass
    s = DummyStorage()

    for inode_name in inode_index:
        upgrade_log.debug('Reorganizing inode %r', inode_name)
        inode = StorageInode(inode_name, inode_index[inode_name], s)

        block_offsets = set()
        for old_block_name in inode.tree:
            if old_block_name.startswith('b'):
                if not old_block_name.startswith('bt'):
                    block_offsets.add(int(old_block_name[1:]))

        for block_offset in sorted(block_offsets):
            old_block_name = 'b%d' % block_offset
            new_block_name = str(block_offset / StorageInode.blocksize)
            old_block = inode.tree[old_block_name]
            new_block = inode.tt.clone(old_block, new_block_name)
            del inode.tree[old_block_name]

        inode['size'] = block_offset + len(new_block.data)
        inode.tree._commit()

@storage_format_upgrade('Convert list of inodes to treetree',
                       upgrade_from={'inode_index_format': None},
                       upgrade_to={'inode_index_format': 'treetree'})
def convert_fs_to_treetree_inode_index(eg):
    """
    Convert a filesystem from the "inode index as as flat list" format to the
    "inode index as treetree" format.
    """

    inode_index_raw = eg.root['inodes']
    inode_index_tt = TreeTree(inode_index_raw, prefix='it')

    all_inode_names = list(inode_index_raw.keys())
    largest_number = -1
    for inode_name in all_inode_names:
        upgrade_log.debug('Moving inode %r to treetree', inode_name)
        inode_index_tt.clone(inode_index_raw[inode_name], inode_name[1:])
        del inode_index_raw[inode_name]
        number = int(inode_name[1:])
        largest_number = max(largest_number, number)

    FeatureBlob(eg.root['features'])['next_inode_number'] = largest_number + 1

all_updates = [
    convert_fs_to_treetree_inodes,
    convert_fs_to_treetree_inode_index,
]
