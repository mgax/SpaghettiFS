import dulwich

class Repo(object):
    def __init__(self, repo_path):
        self.git = dulwich.repo.Repo(repo_path)

    @property
    def _current_tree(self):
        head = self.git.head()
        commit = self.git.commit(head)
        tree = self.git.tree(commit.tree)
        return tree

    def _get_dir(self, dir_path):
        dir_tree = self._current_tree
        for dir_name in dir_path.split('/'):
            dir_entry = dict((i[0], i[2]) for i in dir_tree.iteritems())[dir_name]
            dir_tree = self.git.tree(dir_entry)

        return dir_tree

    def get_file(self, file_path):
        assert file_path.startswith('/')
        dir_path, sep, file_name = ('data'+file_path).rpartition('/')

        dir_tree = self._get_dir(dir_path)
        file_entry = dict((i[0], i[2]) for i in dir_tree.iteritems())[file_name]
        file_blob = self.git.get_blob(file_entry)
        file_data = file_blob.data

        return RepoFile(file_name, file_data)

    def list_files(self, dir_path):
        assert dir_path.startswith('/'), dir_path.endswith('/')
        dir_tree = self._get_dir('data' + dir_path[:-1])
        return [entry[1] for entry in dir_tree.entries()]

class RepoFile(object):
    def __init__(self, name, data):
        self.name = name
        self.data = data
