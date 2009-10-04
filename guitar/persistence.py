import UserDict
import dulwich

class Repo(object):
    def __init__(self, repo_path):
        self.git = dulwich.repo.Repo(repo_path)

    def get_root(self):
        git_id = self.git.commit(self.git.head()).tree
        commit_tree = RepoDir(self.git, git_id, None, None)
        root_tree = commit_tree['data']
        root_tree.name = '[root]'
        root_tree.path = '/'
        return root_tree

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
                if mode == 16384: # directory
                    return RepoDir(self.git, git_id, name, self)
                else: # regular file
                    return RepoFile(self.git, git_id, name, self)
        raise KeyError(key)

    def keys(self):
        return [name for (name, mode, git_id) in self.itertree()]

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
