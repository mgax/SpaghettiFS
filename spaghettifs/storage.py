from time import time
import UserDict
import logging
import binascii
from cStringIO import StringIO

import dulwich

log = logging.getLogger('spaghettifs.storage')
log.setLevel(logging.DEBUG)

class FriendlyTree(object):
    _git_tree = None

    def __init__(self, git, parent_tree, name_in_parent, delegate, git_id):
        self.git = git
        self.parent_tree = parent_tree
        self.name_in_parent = name_in_parent
        self.delegate = delegate
        self.git_id = git_id

    def __enter__(self):
        self._git_tree = self.git.tree(self.git_id)
        return self

    def __exit__(self, e_type, e_value, e_traceback):
        self.git.add_object(self._git_tree)
        self.git_id = self._git_tree.id
        del self._git_tree
        self.parent_tree[self.name_in_parent] = self

    def __setitem__(self, key, value):
        assert self._git_tree is not None
        if value.is_tree:
            self._git_tree[key] = (040000, value.git_id)
        else:
            self._git_tree[key] = (0100644, value.git_id)

    def __delitem__(self, key):
        assert self._git_tree is not None
        del self._git_tree[key]

class GitStorage(object):
    def __init__(self, repo_path):
        self.git = dulwich.repo.Repo(repo_path)
        self.head = self.git.head()
        self.commit_tree_id = self.git.commit(self.head).tree
        log.debug('Loaded storage, head=%s', self.head)

    def get_root(self):
        commit_tree = self.git.tree(self.commit_tree_id)
        root_ls_id = commit_tree['root.ls'][1]
        root_sub_id = commit_tree['root.sub'][1]
        root = StorageDir('root', root_ls_id, root_sub_id, self, self)
        root.path = '/'
        return root

    def get_inode(self, name):
        commit_tree = self.git.tree(self.commit_tree_id)
        inode_tree = self.git.tree(commit_tree['inodes'][1])
        inode_id = inode_tree[name][1]
        return StorageInode(name, inode_id, self)

    def create_inode(self):
        inodes_id = self.git.tree(self.commit_tree_id)['inodes'][1]
        inodes = self.git.tree(inodes_id)
        # TODO: find a better way to choose the inode number
        last_inode_number = max(int(i[0][1:]) for i in inodes.iteritems())
        inode_name = 'i' + str(last_inode_number + 1)

        inode_contents = dulwich.objects.Tree()
        self.git.object_store.add_object(inode_contents)

        inodes[inode_name] = (040000, inode_contents.id)
        self.git.object_store.add_object(inodes)

        self.update_sub('inodes', (040000, inodes.id))

        return self.get_inode(inode_name)

    def update_inode(self, inode_name, inode_contents_id):
        inodes_id = self.git.tree(self.commit_tree_id)['inodes'][1]
        inodes = self.git.tree(inodes_id)
        if inode_contents_id is None:
            del inodes[inode_name]
        else:
            inodes[inode_name] = (040000, inode_contents_id)
        self.git.object_store.add_object(inodes)
        self.update_sub('inodes', (040000, inodes.id))

    def update_sub(self, name, value):
        assert ((name == 'root.ls' and value[0] == 0100644) or
                (name == 'root.sub' and value[0] == 040000) or
                (name == 'inodes' and value[0] == 040000))

        commit_tree = self.git.tree(self.commit_tree_id)
        commit_tree[name] = value

        commit = dulwich.objects.Commit()
        commit.tree = commit_tree.id
        commit.author = commit.committer = "Spaghetti User <noreply@grep.ro>"
        commit.commit_time = commit.author_time = int(time())
        commit.commit_timezone = commit.author_timezone = 2*60*60
        commit.encoding = "UTF-8"
        commit.message = "Auto commit"
        commit.set_parents([self.git.head()])

        log.info('Committing %s', commit_tree.id)

        self.git.object_store.add_object(commit_tree)
        self.git.object_store.add_object(commit)
        self.commit_tree_id = commit_tree.id
        self.git.refs['refs/heads/master'] = commit.id

class StorageDir(UserDict.DictMixin):
    is_dir = True

    def __init__(self, name, ls_id, sub_id, storage, parent):
        self.name = name
        self.ls_id = ls_id # ID of blob that lists our contents
        self.sub_id = sub_id # ID of tree that keeps our subfolders
        self.storage = storage
        self.parent = parent
        log.debug('Loaded folder %s, ls_id=%s, sub_id=%s',
                  repr(name), ls_id, sub_id)

    @property
    def path(self):
        return self.parent.path + self.name + '/'

    def _iter_contents(self):
        ls_data = self.storage.git.get_blob(self.ls_id).data
        for line in ls_data.split('\n'):
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
                    sub = self.storage.git.tree(self.sub_id)
                    child_ls_id = sub[quote(name) + '.ls'][1]
                    try:
                        child_sub_id = sub[quote(name) + '.sub'][1]
                    except KeyError:
                        child_sub_id = None
                    return StorageDir(name, child_ls_id, child_sub_id,
                                      self.storage, self)
                else:
                    inode = self.storage.get_inode(value)
                    return StorageFile(name, inode, self)
        else:
            raise KeyError('Folder entry %s not found' % repr(key))

    def create_file(self, name):
        check_filename(name)
        inode = self.storage.create_inode()
        ls_blob = self.storage.git.get_blob(self.ls_id)
        ls_blob.data += "%s %s\n" % (quote(name), inode.name)
        self.storage.git.object_store.add_object(ls_blob)
        self.ls_id = ls_blob.id
        self.parent.update_sub(self.name + '.ls', (0100644, self.ls_id))
        return self[name]

    def create_directory(self, name):
        check_filename(name)
        log.info('Creating directory %s in %s', repr(name), repr(self.path))

        child_ls_blob = dulwich.objects.Blob.from_string('')
        self.storage.git.object_store.add_object(child_ls_blob)
        self.update_sub(name + '.ls', (0100644, child_ls_blob.id))

        ls_blob = self.storage.git.get_blob(self.ls_id)
        ls_blob.data += "%s /\n" % quote(name)
        self.storage.git.object_store.add_object(ls_blob)
        self.ls_id = ls_blob.id
        self.parent.update_sub(self.name + '.ls', (0100644, self.ls_id))

        return self[name]

    def update_sub(self, name, value):
        assert ((name.endswith('.ls') and value[0] == 0100644) or
                (name.endswith('.sub') and value[0] == 040000))
        log.info('Updating record %s in %s, value=%s',
                 name, repr(self.path), value)
        if self.sub_id is None:
            sub = dulwich.objects.Tree()
        else:
            sub = self.storage.git.tree(self.sub_id)
        if value[1] is None:
            del sub[quote(name)]
        else:
            sub[quote(name)] = value
        self.sub_id = sub.id
        self.storage.git.object_store.add_object(sub)
        self.parent.update_sub(self.name + '.sub',
                               (040000, self.sub_id))

    def remove_ls_entry(self, rm_name):
        ls_data = ''
        for name, value in self._iter_contents():
            if name == rm_name:
                log.debug('Removing ls entry %s from %s',
                          repr(rm_name), repr(self.path))
            else:
                ls_data += '%s %s\n' % (quote(name), value)
        ls_blob = dulwich.objects.Blob.from_string(ls_data)
        self.storage.git.object_store.add_object(ls_blob)
        self.ls_id = ls_blob.id
        self.parent.update_sub(self.name + '.ls',
                               (0100644, self.ls_id))

    def unlink(self):
        log.info('Removing folder %s', repr(self.path))
        self.parent.update_sub(self.name + '.ls', (0100644, None))
        if self.sub_id is not None:
            self.parent.update_sub(self.name + '.sub', (040000, None))
        self.parent.remove_ls_entry(self.name)

class StorageInode(object):
    blocksize = 64*1024 # 64 KB

    def __init__(self, name, tree_id, storage):
        self.name = name
        self.tree_id = tree_id
        self.storage = storage
        log.debug('Loaded inode %s, tree_id=%s', repr(name), tree_id)

    def read_block(self, n):
        block_name = 'b%d' % (n * self.blocksize)
        try:
            block_id = self.storage.git.tree(self.tree_id)[block_name][1]
        except KeyError:
            # TODO: raise exception
            return ''

        log.debug('Reading block %r of inode %r: %r',
                  block_name, self.name, block_id)
        return self.storage.git.get_blob(block_id).data

    def write_block(self, n, data):
        block_name = 'b%d' % (n * self.blocksize)
        block_blob = dulwich.objects.Blob.from_string(data)
        block_id = block_blob.id

        log.debug('Writing block %r of inode %r: %r',
                  block_name, self.name, block_id)
        tree = self.storage.git.tree(self.tree_id)
        tree[block_name] = (0100644, block_id)
        self.storage.git.object_store.add_object(block_blob)
        self.storage.git.object_store.add_object(tree)
        self.tree_id = tree.id
        self.storage.update_inode(self.name, self.tree_id)

    def delete_block(self, n):
        block_name = 'b%d' % (n * self.blocksize)
        log.debug('Removing block %r of inode %r', block_name, self.name)
        tree = self.storage.git.tree(self.tree_id)
        del tree[block_name]
        self.storage.git.object_store.add_object(tree)
        self.tree_id = tree.id
        self.storage.update_inode(self.name, self.tree_id)

    def get_size(self):
        block_tree = self.storage.git.tree(self.tree_id)

        last_block_offset = None
        for entry in block_tree.iteritems():
            block_offset = int(entry[0][1:])
            if block_offset > last_block_offset:
                last_block_offset = block_offset
                last_block_id = entry[2]

        if last_block_offset is None:
            return 0
        else:
            last_block_blob = self.storage.git.get_blob(last_block_id)
            return last_block_offset + len(last_block_blob.data)

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
        self.storage.update_inode(self.name, None)

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

    @property
    def data(self):
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
