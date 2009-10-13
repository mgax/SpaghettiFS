from time import time

import dulwich

class EasyTree(object):
    _git_tree = None

    def __init__(self, git_repo, git_id=None):
        self.git = git_repo
        if git_id is None:
            git_tree = dulwich.objects.Tree()
            self.git.object_store.add_object(git_tree)
            git_id = git_tree.id
        self.git_id = git_id

    def __enter__(self):
        assert self._git_tree is None
        self._git_tree = dulwich.objects.Tree()

    def __exit__(self, exc_type, exc_value, exc_traceback):
        assert self._git_tree is not None
        self.git.object_store.add_object(self._git_tree)
        self.git_id = self._git_tree.id
        del self._git_tree

    def __setitem__(self, key, value):
        assert self._git_tree is not None
        assert value._git_tree is None
        self._git_tree[key] = (040000, value.git_id)

class EasyGit(object):
    def __init__(self, git_repo):
        self.git = git_repo

    def new_tree(self):
        return EasyTree(self.git)

    def commit(self, author, message, tree):
        commit_time = int(time())

        git_commit = dulwich.objects.Commit()
        git_commit.commit_time = commit_time
        git_commit.author_time = commit_time
        git_commit.commit_timezone = 2*60*60
        git_commit.author_timezone = 2*60*60
        git_commit.author = author
        git_commit.committer = author
        git_commit.message = message
        git_commit.encoding = "UTF-8"
        git_commit.tree = tree.git_id

        self.git.object_store.add_object(git_commit)
        self.git.refs['refs/heads/master'] = git_commit.id

    @classmethod
    def new(cls, repo_path, bare=False):
        assert bare is True
        git_repo = dulwich.repo.Repo.init_bare(repo_path)
        return cls(git_repo)
