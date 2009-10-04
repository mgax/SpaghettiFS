import UserDict
import dulwich

class Repo(object):
    def __init__(self, repo_path):
        self.git = dulwich.repo.Repo(repo_path)

    def get_root(self):
        git_id = self.git.commit(self.git.head()).tree
        commit_tree = RepoDir(self.git, git_id, None)
        root_tree = commit_tree['data']
        root_tree.name = '[root]'
        return root_tree

class RepoDir(UserDict.DictMixin):
    is_dir = True

    def __init__(self, git, git_id, name):
        self.git = git
        self.git_id = git_id
        self.name = name
        #self.items = [item[0] for item in self.tree.iteritems()]

    def itertree(self):
        return self.git.tree(self.git_id).iteritems()

    def __getitem__(self, key):
        for name, mode, git_id in self.itertree():
            if name == key:
                if mode == 16384: # directory
                    return RepoDir(self.git, git_id, name)
                else: # regular file
                    return RepoFile(self.git, git_id, name)
        raise KeyError(key)

    def keys(self):
        return [name for (name, mode, git_id) in self.itertree()]


class RepoFile(object):
    is_dir = False

    def __init__(self, git, git_id, name):
        self.git = git
        self.git_id = git_id
        self.name = name
        self.blob = self.git.get_blob(git_id)
        self.data = self.blob.data
        self.size = len(self.blob.data)
