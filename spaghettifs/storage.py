import os
from time import time
import UserDict
import logging
import binascii
from cStringIO import StringIO
from itertools import chain
import weakref

from easygit import EasyGit
from treetree import TreeTree

log = logging.getLogger('spaghettifs.storage')
log.setLevel(logging.DEBUG)

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
        eg.commit(cls.commit_author, 'Created empty filesystem')

        return cls(repo_path)

    def __init__(self, repo_path, autocommit=True):
        self.eg = EasyGit.open_repo(repo_path)
        self.autocommit = autocommit
        log.debug('Loaded storage, autocommit=%r, HEAD=%r',
                  autocommit, self.eg.get_head_id())
        self._inode_cache = {}

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

        inode_tree = self.eg.root['inodes'][name]
        inode = StorageInode(name, inode_tree, self)
        self._inode_cache[name] = weakref.ref(inode)

        return inode

    def create_inode(self):
        inodes = self.eg.root['inodes']
        # TODO: find a better way to choose the inode number
        inode_numbers = (int(name[1:]) for name in inodes)
        last_inode_number = max(chain([0], inode_numbers))
        inode_name = 'i' + str(last_inode_number + 1)
        inode_tree = inodes.new_tree(inode_name)
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

def fsck(repo_path, out):
    count = {'errors': 0}
    def error(msg):
        count['errors'] += 1
        print>>out, msg

    def walk_folder(parent, folder_name):
        for name, value in iter_entries(parent[folder_name+'.ls'].data):
            if value == '/':
                walk_folder(parent[folder_name+'.sub'], name)
            else:
                check_inode(value)

    def check_inode(inode_name):
        if inode_name not in inodes:
            error('missing inode %r' % inode_name)

    eg = EasyGit.open_repo(repo_path)
    inodes = eg.root['inodes']
    walk_folder(eg.root, 'root')

    if count['errors']:
        print>>out, 'done; %d errors' % count['errors']
    else:
        print>>out, 'done; all ok'
