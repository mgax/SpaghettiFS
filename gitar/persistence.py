import gitlib

class Repo(object):
    def __init__(self, repo_path):
        self.git = gitlib.Repository(repo_path)

    @property
    def _current_tree(self):
        head = self.git.find_head()
        commit = self.git.getcommit(head)
        tree = self.git.gettree(commit.tree)
        return tree

    def get_file(self, file_path):
        dir_path, sep, file_name = ('data'+file_path).rpartition('/')

        tree = self._current_tree
        for dir_name in dir_path.split('/'):
            dir_entry = dict(tree.entries())[dir_name]
            assert dir_entry.is_dir()
            tree = self.git.gettree(dir_entry.name)

        file_entry = dict(tree.entries())[file_name]
        assert not file_entry.is_dir()
        file_blob = self.git.getblob(file_entry.name)
        file_data = file_blob.text

        return RepoFile(file_name, file_data)

class RepoFile(object):
    def __init__(self, name, data):
        self.name = name
        self.data = data
