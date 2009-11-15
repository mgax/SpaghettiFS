from time import time
import weakref
import logging

import dulwich

log = logging.getLogger('spaghettifs.easygit')
log.setLevel(logging.DEBUG)

class EasyTree(object):
    def __init__(self, git_repo, git_id=None, parent=None, name=None):
        self.parent = parent
        self.name = name
        self.git = git_repo
        if git_id is None:
            log.debug('tree %r: creating blank git tree', self.name)
            git_tree = dulwich.objects.Tree()
            self.git.object_store.add_object(git_tree)
            git_id = git_tree.id
        log.debug('tree %r: loading git tree %r', self.name, git_id)
        self._git_tree = self.git.tree(git_id)
        self._ctx_count = 0
        self._loaded = dict()
        self._dirty = dict()

    def _set_dirty(self, name, value):
        log.debug('tree %r: setting dirty entry %r (%r)',
                  self.name, name, value)
        if self.parent and not self._dirty:
            log.debug('tree %r: propagating "dirty" state', self.name)
            self.parent._set_dirty(self.name, self)
        self._dirty[name] = value

    def new_tree(self, name):
        log.debug('tree %r: creating child tree %r', self.name, name)
        t = EasyTree(self.git, None, self, name)
        self._set_dirty(name, t)
        return self[name]

    def new_blob(self, name):
        log.debug('tree %r: creating child blob %r', self.name, name)
        b = EasyBlob(self.git, None, self, name)
        self._set_dirty(name, b)
        return self[name]

    def __enter__(self):
        self._ctx_count += 1
        log.debug('tree %r: entering context manager (count=%d)',
                  self.name, self._ctx_count)
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        log.debug('tree %r: exiting context manager (count=%d)',
                  self.name, self._ctx_count)
        assert self._ctx_count > 0
        self._ctx_count -= 1

    def _commit(self):
        log.debug('tree %r: committing', self.name)
        assert self._ctx_count == 0

        for name, value in self._dirty.iteritems():
            if value is None:
                log.debug('tree %r: removing entry %r', self.name, name)
                del self._git_tree[name]
                continue

            value_git_id = value._commit()
            if isinstance(value, EasyTree):
                log.debug('tree %r: updating tree %r', self.name, name)
                self._git_tree[name] = (040000, value_git_id)
            elif isinstance(value, EasyBlob):
                log.debug('tree %r: updating blob %r', self.name, name)
                self._git_tree[name] = (0100644, value_git_id)
            else:
                assert False

        self._dirty.clear()

        self.git.object_store.add_object(self._git_tree)
        git_id = self._git_tree.id
        log.debug('tree %r: finished commit, id=%r', self.name, git_id)
        return git_id

    def __getitem__(self, name):
        if name in self._loaded:
            value = self._loaded[name]()
            if value is None:
                log.debug('tree %r: weakref to %r has expired',
                          self.name, name)
                del self._loaded[name]
            else:
                log.debug('tree %r: returning %r from cache',
                          self.name, name)
                return value

        if name in self._dirty:
            value = self._dirty[name]
            if value is None:
                raise KeyError(name)
            log.debug('tree %r: returning %r from dirty', self.name, name)

        else:
            mode, child_git_id = self._git_tree[name]
            if mode == 040000:
                log.debug('tree %r: loading child tree %r', self.name, name)
                value = EasyTree(self.git, child_git_id, self, name)
            elif mode == 0100644:
                log.debug('tree %r: loading child blob %r', self.name, name)
                value = EasyBlob(self.git, child_git_id, self, name)
            else:
                raise ValueError('Unexpected mode %r' % mode)

        self._loaded[name] = weakref.ref(value)
        return value

    def __delitem__(self, name):
        self._set_dirty(name, None)
        if name in self._loaded:
            del self._loaded[name]

    def __iter__(self):
        for name in self.keys():
            yield name

    def keys(self):
        names = set(name for name, e0, e1 in self._git_tree.iteritems())
        names.update(set(self._dirty.iterkeys()))
        for name, value in self._dirty.iteritems():
            if value is None:
                names.remove(name)

        return list(names)

    def remove(self):
        del self.parent[self.name]

class EasyBlob(object):
    def __init__(self, git_repo, git_id=None, parent=None, name=None):
        self.parent = parent
        self.name = name
        self.git = git_repo
        if git_id is None:
            log.debug('blob %r: creating blank git blob', self.name)
            git_blob = dulwich.objects.Blob.from_string('')
            self.git.object_store.add_object(git_blob)
            git_id = git_blob.id
        log.debug('blob %r: loading git blob %r', self.name, git_id)
        self._git_blob = self.git.get_blob(git_id)
        self._ctx_count = 0

    def __enter__(self):
        self._ctx_count += 1
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        assert self._ctx_count > 0
        self._ctx_count -= 1

    def _get_data(self):
        return self._git_blob.data

    def _set_data(self, value):
        log.debug('blob %r: updating value', self.name)
        self._git_blob = dulwich.objects.Blob.from_string(value)
        self.parent._set_dirty(self.name, self)

    data = property(_get_data, _set_data)

    def remove(self):
        del self.parent[self.name]

    def _commit(self):
        assert self._ctx_count == 0

        self.git.object_store.add_object(self._git_blob)
        git_id = self._git_blob.id
        log.debug('blob %r: finished commit, id=%r', self.name, git_id)
        return git_id

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

    def commit(self, author, message, parents=[], branch='master'):
        log.debug('easygit repo: starting commit')
        for parent_id in parents:
            assert self.git.commit(parent_id)

        root_git_id = self.root._commit()

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
        git_commit.tree = root_git_id
        git_commit.parents = parents

        self.git.object_store.add_object(git_commit)
        self.git.refs['refs/heads/%s' % branch] = git_commit.id
        log.debug('easygit repo: finished commit, id=%r', git_commit.id)

    def get_head_id(self, name="master"):
        return self.git.refs['refs/heads/%s' % name]

    @classmethod
    def new_repo(cls, repo_path, bare=False):
        log.debug('easygit creating repository at %r', repo_path)
        assert bare is True
        git_repo = dulwich.repo.Repo.init_bare(repo_path)
        return cls(git_repo)

    @classmethod
    def open_repo(cls, repo_path):
        log.debug('easygit opening repository at %r', repo_path)
        git_repo = dulwich.repo.Repo(repo_path)
        return cls(git_repo)
