from time import time
import weakref

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
        self._ctx_count = 0
        self._loaded = dict()

    def _set(self, name, value):
        if self._git_tree is None:
            with self:
                return self._set(name, value)

        if value is None:
            del self._git_tree[name]

        elif isinstance(value, EasyTree):
            assert value._git_tree is None
            self._git_tree[name] = (040000, value.git_id)

        elif isinstance(value, EasyBlob):
            assert value._git_blob is None
            self._git_tree[name] = (0100644, value.git_id)

        else:
            assert False

    def new_tree(self, name):
        t = EasyTree(self.git, None, self, name)
        self._set(name, t)
        return self[name]

    def new_blob(self, name):
        b = EasyBlob(self.git, None, self, name)
        self._set(name, b)
        return self[name]

    def __enter__(self):
        if self._git_tree is None:
            assert self._ctx_count == 0
            self._git_tree = self.git.tree(self.git_id)
        self._ctx_count += 1
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        assert self._ctx_count > 0
        assert self._git_tree is not None
        self._ctx_count -= 1
        if self._ctx_count > 0:
            return

        self.git.object_store.add_object(self._git_tree)
        self.git_id = self._git_tree.id
        del self._git_tree

        if self.parent is not None:
            with self.parent as p:
                p._set(self.name, self)

    def __getitem__(self, name):
        if name in self._loaded:
            value = self._loaded[name]()
            if value is None:
                del self._loaded[name]
            else:
                return value

        if self._git_tree is None:
            with self:
                return self[name]

        mode, child_git_id = self._git_tree[name]
        if mode == 040000:
            value = EasyTree(self.git, child_git_id, self, name)
        elif mode == 0100644:
            value = EasyBlob(self.git, child_git_id, self, name)
        else:
            raise ValueError('Unexpected mode %r' % mode)

        self._loaded[name] = weakref.ref(value)
        return value

    def __delitem__(self, name):
        self._set(name, None)

    def __iter__(self):
        with self:
            for name, mode, child_git_id in self._git_tree.iteritems():
                yield name

    def keys(self):
        return [name for name in self]

    def remove(self):
        del self.parent[self.name]

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
        self._ctx_count = 0

    def __enter__(self):
        if self._git_blob is None:
            assert self._ctx_count == 0
            self._git_blob = self.git.get_blob(self.git_id)
        self._ctx_count += 1
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        assert self._ctx_count > 0
        assert self._git_blob is not None
        self._ctx_count -= 1
        if self._ctx_count > 0:
            return

        self.git.object_store.add_object(self._git_blob)
        self.git_id = self._git_blob.id
        del self._git_blob

        if self.parent is not None:
            with self.parent as p:
                p._set(self.name, self)

    def _get_data(self):
        if self._git_blob is None:
            with self:
                return self._get_data()
        return self._git_blob.data

    def _set_data(self, value):
        if self._git_blob is None:
            with self:
                return self._set_data(value)
        self._git_blob.data = value

    data = property(_get_data, _set_data)

    def remove(self):
        del self.parent[self.name]

class EasyGit(object):
    def __init__(self, git_repo):
        self.git = git_repo
        try:
            git_commit_id = self.git.head()
        except:
            root_id = None
        else:
            git_commit = self.git.commit(self.git.head())
            root_id = git_commit.tree

        self.root = EasyTree(self.git, root_id, None, '[ROOT]')

    def commit(self, author, message, parents=[]):
        for parent_id in parents:
            assert self.git.commit(parent_id)

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
        git_commit.tree = self.root.git_id
        git_commit.parents = parents

        self.git.object_store.add_object(git_commit)
        self.git.refs['refs/heads/master'] = git_commit.id

    def get_head_id(self):
        return self.git.head()

    @classmethod
    def new_repo(cls, repo_path, bare=False):
        assert bare is True
        git_repo = dulwich.repo.Repo.init_bare(repo_path)
        return cls(git_repo)

    @classmethod
    def open_repo(cls, repo_path):
        git_repo = dulwich.repo.Repo(repo_path)
        return cls(git_repo)
