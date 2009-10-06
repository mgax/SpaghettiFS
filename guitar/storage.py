from time import time
import UserDict
import dulwich

class Repo(object):
    def __init__(self, repo_path):
        self.git = dulwich.repo.Repo(repo_path)
        self.tree_git_id = self.git.commit(self.git.head()).tree

    def get_root(self):
        commit_tree = self.git.tree(self.tree_git_id)
        root_id = dict((i[0], i[2]) for i in commit_tree.iteritems())['data']
        root_tree = RepoDir(self.git, root_id, '[root]', self)
        root_tree.path = '/'
        return root_tree

    def update(self, mode, name, git_id, msg):
        commit_tree = self.git.tree(self.tree_git_id)
        commit_tree.add(040000, 'data', git_id)
        self.git.object_store.add_object(commit_tree)
        self.tree_git_id = commit_tree.id

        commit = dulwich.objects.Commit()
        commit.tree = self.tree_git_id
        commit.author = commit.committer = "Guitar User <noreply@grep.ro>"
        commit.commit_time = commit.author_time = int(time())
        commit.commit_timezone = commit.author_timezone = 2*60*60
        commit.encoding = "UTF-8"
        commit.message = "Auto commit: %s" % msg
        self.git.object_store.add_object(commit)
        self.git.refs['refs/heads/master'] = commit.id

class RepoDir(UserDict.DictMixin):
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
                    return RepoDir(self.git, git_id, name, self)
                else: # regular file
                    return RepoFile(self.git, git_id, name, self)
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

class RepoFile(object):
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
