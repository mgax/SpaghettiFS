from time import time
import UserDict
import logging
import binascii

import dulwich

log = logging.getLogger('spaghettifs.storage')
log.setLevel(logging.DEBUG)

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
            name, value = line.rsplit(' ', 1)
            yield unquote(name), value
            #yield name, value

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
    def __init__(self, name, tree_id, storage):
        self.name = name
        self.tree_id = tree_id
        self.storage = storage
        log.debug('Loaded inode %s, tree_id=%s', repr(name), tree_id)

    def get_data(self):
        git = self.storage.git
        try:
            block0_id = git.tree(self.tree_id)['b0'][1]
        except KeyError:
            return ''
        log.debug('Loading block 0 of inode %s: %s',
                  repr(self.name), block0_id)
        block0 = git.get_blob(block0_id)
        return block0.data

    def _update_data(self, new_data):
        block0 = dulwich.objects.Blob.from_string(new_data)
        self.storage.git.object_store.add_object(block0)
        tree = self.storage.git.tree(self.tree_id)
        tree['b0'] = (0100644, block0.id)
        self.storage.git.object_store.add_object(tree)
        self.tree_id = tree.id
        self.storage.update_inode(self.name, self.tree_id)

    def write_data(self, data, offset):
        log.info('Inode %s writing %d bytes at offset %d',
                 repr(self.name), len(data), offset)

        current_data = self.get_data()
        end = offset + len(data)

        if len(current_data) <= offset:
            new_data = (current_data +
                        '\0' * (offset - len(current_data)) +
                        data)

        elif len(current_data) >= (end):
            new_data = (current_data[:offset] +
                        data +
                        current_data[end:])

        else:
            new_data = (current_data[:offset] +
                        data)

        self._update_data(new_data)

    def truncate(self, new_size):
        log.info("Truncating inode %s, new size %d", repr(self.name), new_size)

        current_data = self.get_data()
        current_size = len(current_data)

        if current_size > new_size:
            self._update_data(current_data[:new_size])
        elif current_size < new_size:
            padding = '\0' * (new_size - current_size)
            self._update_data(current_data + padding)
        else:
            pass

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
        return len(self.data)

    @property
    def data(self):
        return self.inode.get_data()

    def write_data(self, data, offset):
        return self.inode.write_data(data, offset)

    def truncate(self, new_size):
        return self.inode.truncate(new_size)

    def unlink(self):
        log.info('Unlinking file %s', repr(self.path))
        self.parent.remove_ls_entry(self.name)
        self.inode.unlink()

def quote(name):
    return binascii.b2a_qp(name, quotetabs=True, istext=False)

unquote = binascii.a2b_qp

def check_filename(name):
    if name in ('.', '..', '') or '/' in name:
        raise ValueError("Bad filename %r" % name)
