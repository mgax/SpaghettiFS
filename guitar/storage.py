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
        tree.add(mode, name, git_id)
        self.git.object_store.add_object(tree)
        self.git_id = tree.id
        self.parent.update(040000, self.name, self.git_id, msg)

    def create_file(self, name):
        # TODO: check filename
        blob = dulwich.objects.Blob.from_string('')
        self.git.object_store.add_object(blob)
        msg = "creating file %s" % (self.path + name)
        self.update(0100644, name, blob.id, msg)
        return self[name]

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