import dulwich

class EasyGit(object):
    @classmethod
    def new(cls, repo_path, bare=False):
        assert bare is True
        repo = dulwich.repo.Repo.init_bare(repo_path)
