import unittest
import tempfile
import shutil
from os import path
import logging

from spaghettifs.storage import GitStorage

test_git_path = path.join(path.dirname(__file__), 'repo.git')

stderr_handler = logging.StreamHandler()
stderr_handler.setLevel(logging.ERROR)
logging.getLogger('spaghettifs').addHandler(stderr_handler)

class SpaghettiTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_path = path.join(self.tmpdir, path.basename(test_git_path))
        shutil.copytree(test_git_path, self.repo_path)
        self.repo = GitStorage(self.repo_path)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

def setup_logger(log_level):
    import logging
    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(getattr(logging, log_level))
    logging.getLogger('spaghettifs').addHandler(stderr_handler)
