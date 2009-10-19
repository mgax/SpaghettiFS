from time import time
import UserDict
import logging
import binascii
from cStringIO import StringIO

import easygit

log = logging.getLogger('spaghettifs.storage')
log.setLevel(logging.DEBUG)

class GitStorage(object):
    def __init__(self, repo_path):
        self.eg = easygit.EasyGit.open_repo(repo_path)
        log.debug('Loaded storage')

    def get_root(self):
        commit_tree = self.eg.root
        root_ls = commit_tree['root.ls']
        root_sub = commit_tree['root.sub']
        root = StorageDir('root', root_ls, root_sub, '/', self, None)
        root.path = '/'
        return root

    def get_inode(self, name):
        inode_tree = self.eg.root['inodes'][name]
        return StorageInode(name, inode_tree, self)

    def create_inode(self):
        inodes = self.eg.root['inodes']
        # TODO: find a better way to choose the inode number
        last_inode_number = max(int(name[1:]) for name in inodes)
        inode_name = 'i' + str(last_inode_number + 1)
        inodes.new_tree(inode_name)
        return self.get_inode(inode_name)

    def commit(self):
        log.info('Committing')

        self.eg.commit(author="Spaghetti User <noreply@grep.ro>",
                       message="Auto commit",
                       parents=[self.eg.get_head_id()])

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
        for line in self.ls_blob.data.split('\n'):
            if not line:
                continue
            try:
                name, value = line.rsplit(' ', 1)
            except ValueError, e:
                log.error('Bad line in ls file %r: %r', self.path, line)
                raise
            yield unquote(name), value

    def keys(self):
        for name, value in self._iter_contents():
            yield name

    def __getitem__(self, key):
        for name, value in self._iter_contents():
            if key == name:
                if value == '/':
                    qname = quote(name)
                    child_ls = self.sub_tree[qname + '.ls']
                    try:
                        child_sub = self.sub_tree[qname + '.sub']
                    except KeyError:
                        child_sub = self.sub_tree.new_tree(qname + '.sub')
                        self.storage.commit()
                    return StorageDir(name, child_ls, child_sub,
                                      self.path + name + '/',
                                      self.storage, self)
                else:
                    inode = self.storage.get_inode(value)
                    return StorageFile(name, inode, self)
        else:
            raise KeyError('Folder entry %s not found' % repr(key))

    def create_file(self, name):
        check_filename(name)
        log.info('Creating file %s in %s', repr(name), repr(self.path))

        inode = self.storage.create_inode()
        with self.ls_blob as b:
            b.data += "%s %s\n" % (quote(name), inode.name)

        self.storage.commit()

        return self[name]

    def create_directory(self, name):
        check_filename(name)
        log.info('Creating directory %s in %s', repr(name), repr(self.path))

        qname = quote(name)
        with self.sub_tree as st:
            child_ls_blob = st.new_blob(qname + '.ls')
        with self.ls_blob as b:
            b.data += "%s /\n" % qname

        self.storage.commit()

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

        self.storage.commit()

    def unlink(self):
        log.info('Removing folder %s', repr(self.path))

        self.ls_blob.remove()
        self.sub_tree.remove()
        self.parent.remove_ls_entry(self.name)

        self.storage.commit()

class StorageInode(object):
    blocksize = 64*1024 # 64 KB

    def __init__(self, name, tree, storage):
        self.name = name
        self.tree = tree
        self.storage = storage
        log.debug('Loaded inode %r', name)

    def read_block(self, n):
        block_name = 'b%d' % (n * self.blocksize)
        log.debug('Reading block %r of inode %r', block_name, self.name)
        try:
            block = self.tree[block_name]
        except KeyError:
            return ''
        else:
            return block.data

    def write_block(self, n, data):
        block_name = 'b%d' % (n * self.blocksize)
        log.debug('Writing block %r of inode %r', block_name, self.name)
        if block_name in self.tree:
            block = self.tree[block_name]
        else:
            block = self.tree.new_blob(block_name)
        block.data = data

        self.storage.commit()

    def delete_block(self, n):
        block_name = 'b%d' % (n * self.blocksize)
        log.debug('Removing block %r of inode %r', block_name, self.name)
        del self.tree[block_name]

        self.storage.commit()

    def get_size(self):
        last_block_offset = None
        for block_name in self.tree:
            block_offset = int(block_name[1:])
            if block_offset > last_block_offset:
                last_block_offset = block_offset
                last_block_name = block_name

        if last_block_offset is None:
            return 0
        else:
            last_block = self.tree[last_block_name]
            return last_block_offset + len(last_block.data)

    def read_data(self, offset, length):
        end = offset + length
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
        current_size = self.get_size()
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

    def truncate(self, new_size):
        log.info("Truncating inode %s, new size %d", repr(self.name), new_size)

        current_size = self.get_size()
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

    def unlink(self):
        log.info('Unlinking inode %s', repr(self.name))
        self.tree.remove()
        self.storage.commit()

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
        return self.inode.get_size()

    def _read_all_data(self):
        return self.read_data(0, self.inode.get_size())

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
