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

    def _get_dir(self, dir_path):
        dir_tree = self._current_tree
        for dir_name in dir_path.split('/'):
            dir_entry = dict(dir_tree.entries())[dir_name]
            assert dir_entry.is_dir()
            dir_tree = self.git.gettree(dir_entry.name)

        return dir_tree

    def get_file(self, file_path):
        assert file_path.startswith('/')
        dir_path, sep, file_name = ('data'+file_path).rpartition('/')

        dir_tree = self._get_dir(dir_path)
        file_entry = dict(dir_tree.entries())[file_name]
        assert not file_entry.is_dir()
        file_blob = self.git.getblob(file_entry.name)
        file_data = file_blob.text

        return RepoFile(file_name, file_data)

    def list_files(self, dir_path):
        assert dir_path.startswith('/'), dir_path.endswith('/')
        dir_tree = self._get_dir('data' + dir_path[:-1])
        return [entry[0] for entry in dir_tree.entries()]

class RepoFile(object):
    def __init__(self, name, data):
        self.name = name
        self.data = data
