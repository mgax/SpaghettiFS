from time import time

import dulwich

class EasyTree(object):
    _git_tree = None

    def __init__(self, git_repo, git_id=None, parent=None, name=None):
        self.git = git_repo
        if git_id is None:
            git_tree = dulwich.objects.Tree()
            self.git.object_store.add_object(git_tree)
            git_id = git_tree.id
        self.git_id = git_id
        self.parent = parent
        self.name = name

    def _set(self, key, value):
        assert self._git_tree is not None
        if isinstance(value, EasyTree):
            assert value._git_tree is None
            self._git_tree[key] = (040000, value.git_id)
        elif isinstance(value, EasyBlob):
            assert value._git_blob is None
            self._git_tree[key] = (0100644, value.git_id)
        else:
            assert False

    def __enter__(self):
        assert self._git_tree is None
        self._git_tree = dulwich.objects.Tree()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        assert self._git_tree is not None
        self.git.object_store.add_object(self._git_tree)
        self.git_id = self._git_tree.id
        del self._git_tree

        if self.parent is not None:
            with self.parent as p:
                p._set(self.name, self)

    def __getitem__(self, key):
        mode, child_git_id = self.git.tree(self.git_id)[key]
        if mode == 040000:
            return EasyTree(self.git, child_git_id, self, key)
        elif mode == 0100644:
            return EasyBlob(self.git, child_git_id, self, key)
        else:
            raise ValueError('Unexpected mode %r' % mode)

    def __iter__(self):
        git_tree = self.git.tree(self.git_id)
        for name, mode, child_git_id in git_tree.iteritems():
            yield name

    def keys(self):
        return [name for name in self]

class EasyBlob(object):
    _git_blob = None

    def __init__(self, git_repo, git_id=None, parent=None, name=None):
        self.git = git_repo
        if git_id is None:
            git_blob = dulwich.objects.Blob.from_string('')
            self.git.object_store.add_object(git_blob)
            git_id = git_blob.id
        self.git_id = git_id
        self.parent = parent
        self.name = name

    def __enter__(self):
        assert self._git_blob is None
        self._git_blob = dulwich.objects.Blob.from_string('')
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        assert self._git_blob is not None
        self.git.object_store.add_object(self._git_blob)
        self.git_id = self._git_blob.id
        del self._git_blob

        if self.parent is not None:
            with self.parent as p:
                p._set(self.name, self)

    def get_data(self):
        return self.git.get_blob(self.git_id).data

    def set_data(self, value):
        assert self._git_blob is not None
        self._git_blob.data = value

    data = property(get_data, set_data)

class EasyGit(object):
    def __init__(self, git_repo):
        self.git = git_repo

    def get_root(self):
        git_commit = self.git.commit(self.git.head())
        return EasyTree(self.git, git_commit.tree)

    def new_tree(self):
        return EasyTree(self.git)

    def new_blob(self):
        return EasyBlob(self.git)

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
    def new_repo(cls, repo_path, bare=False):
        assert bare is True
        git_repo = dulwich.repo.Repo.init_bare(repo_path)
        return cls(git_repo)

    @classmethod
    def open_repo(cls, repo_path):
        git_repo = dulwich.repo.Repo(repo_path)
        return cls(git_repo)
