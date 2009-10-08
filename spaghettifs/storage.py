from time import time
import UserDict
import logging

import dulwich

log = logging.getLogger('spaghettifs.storage')
log.setLevel(logging.DEBUG)

class GitStorage(object):
    def __init__(self, repo_path):
        self.git = dulwich.repo.Repo(repo_path)
        self.tree_git_id = self.git.commit(self.git.head()).tree

    def get_root(self):
        commit_tree = self.git.tree(self.tree_git_id)
        root_id = dict((i[0], i[2]) for i in commit_tree.iteritems())['data']
        root_tree = StorageDir(self.git, root_id, '[root]', self)
        root_tree.path = '/'
        return root_tree

    def update(self, mode, name, git_id, msg):
        commit_tree = self.git.tree(self.tree_git_id)
        commit_tree.add(040000, 'data', git_id)
        self.git.object_store.add_object(commit_tree)
        self.tree_git_id = commit_tree.id

        commit = dulwich.objects.Commit()
        commit.tree = self.tree_git_id
        commit.author = commit.committer = "Spaghetti User <noreply@grep.ro>"
        commit.commit_time = commit.author_time = int(time())
        commit.commit_timezone = commit.author_timezone = 2*60*60
        commit.encoding = "UTF-8"
        commit.message = "Auto commit: %s" % msg
        self.git.object_store.add_object(commit)
        self.git.refs['refs/heads/master'] = commit.id
del GitStorage

class StorageDir(UserDict.DictMixin):
    is_dir = True

    def __init__(self, git, git_id, name, parent):
        self.git = git
        self.git_id = git_id
        self.name = name
        self.parent = parent

    @property
    def path(self):
        return self.parent.path + self.name + '/'

    def itertree(self):
        return self.git.tree(self.git_id).iteritems()

    def __getitem__(self, key):
        for name, mode, git_id in self.itertree():
            if name == key:
                if mode == 040000: # directory
                    return StorageDir(self.git, git_id, name, self)
                else: # regular file
                    return StorageFile(self.git, git_id, name, self)
        raise KeyError(key)

    def keys(self):
        return [name for (name, mode, git_id) in self.itertree()]

    def update(self, mode, name, git_id, msg):
        tree = self.git.tree(self.git_id)
        if git_id is None:
            del tree[name]
        else:
            tree.add(mode, name, git_id)
        self.git.object_store.add_object(tree)
        self.git_id = tree.id
        self.parent.update(040000, self.name, self.git_id, msg)

    def create_file(self, name):
        # TODO: check name
        blob = dulwich.objects.Blob.from_string('')
        self.git.object_store.add_object(blob)
        msg = "creating file %s" % (self.path + name)
        self.update(0100644, name, blob.id, msg)
        return self[name]

    def create_directory(self, name):
        # TODO: check name
        tree = dulwich.objects.Tree()
        self.git.object_store.add_object(tree)
        msg = "creating directory %s" % (self.path + name)
        self.update(040000, name, tree.id, msg)
        return self[name]

    def unlink(self):
        msg = "removing directory %s" % self.path
        self.parent.update(0, self.name, None, msg)
del StorageDir

class StorageFile(object):
    is_dir = False

    def __init__(self, git, git_id, name, parent):
        self.git = git
        self.git_id = git_id
        self.name = name
        self.parent = parent
        self.blob = self.git.get_blob(git_id)
        self.data = self.blob.data
        self.size = len(self.blob.data)

    @property
    def path(self):
        return self.parent.path + self.name

    def _update_data(self, new_data, msg):
        self.data = new_data
        self.size = len(self.data)
        self.blob = dulwich.objects.Blob.from_string(self.data)
        self.git.object_store.add_object(self.blob)
        self.git_id = self.blob.id
        self.parent.update(0100644, self.name, self.git_id, msg)

    def write_data(self, data, offset):
        current_data = self.data
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

        msg = ("updating file %s " % self.path +
               "(offset %d, size %d)" % (offset, len(data)))
        self._update_data(new_data, msg)

    def truncate(self, size):
        msg = "truncating file %s (new size %d)" % (self.path, size)
        if len(self.data) > size:
            self._update_data(self.data[:size], msg)
        elif len(self.data) < size:
            self._update_data(self.data + '\0' * (size - len(data)), msg)
        else:
            pass

    def unlink(self):
        msg = "removing file %s" % self.path
        self.parent.update(0, self.name, None, msg)
del StorageFile

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
        last_inode_name = max(i[0] for i in inodes.iteritems())
        inode_name = 'i' + str(int(last_inode_name[1:]) + 1)

        inode_contents = dulwich.objects.Tree()
        self.git.object_store.add_object(inode_contents)

        inodes[inode_name] = (040000, inode_contents.id)
        self.git.object_store.add_object(inodes)

        self.update_sub('inodes', (040000, inodes.id))

        return self.get_inode(inode_name)

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
        ls_blob = self.storage.git.get_blob(self.ls_id)
        for line in ls_blob.data.strip().split('\n'):
            yield line.split(' ')

    def keys(self):
        for name, value in self._iter_contents():
            yield name

    def __getitem__(self, key):
        for name, value in self._iter_contents():
            if key == name:
                if value == '/':
                    sub = self.storage.git.tree(self.sub_id)
                    child_ls_id = sub[name + '.ls'][1]
                    try:
                        child_sub_id = sub[name + '.sub'][1]
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
        # TODO: check name
        # TODO: test creating files & folders in various places
        inode = self.storage.create_inode()
        ls_blob = self.storage.git.get_blob(self.ls_id)
        ls_blob.data += "%s %s\n" % (name, inode.name)
        self.storage.git.object_store.add_object(ls_blob)
        self.ls_id = ls_blob.id
        self.parent.update_sub(self.name + '.ls', (0100644, self.ls_id))
        return self[name]

    def update_sub(self, name, value):
        assert ((name.endswith('.ls') and value[0] == 0100644) or
                (name.endswith('.sub') and value[0] == 040000))
        log.info('Updating record %s in %s, value=%s',
                 name, repr(self.path), value)
        sub = self.storage.git.tree(self.sub_id)
        sub[name] = value
        self.sub_id = sub.id
        self.storage.git.object_store.add_object(sub)
        self.parent.update_sub(self.name + '.sub', (040000, self.sub_id))

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
