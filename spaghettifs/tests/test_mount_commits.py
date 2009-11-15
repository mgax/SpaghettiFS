from os import path

import dulwich

from test_filesystem import SpaghettiMountTestCase
from spaghettifs import filesystem

class MountCommits(SpaghettiMountTestCase):
    def tearDown(self):
        if self.mounted:
            self.umount()
        super(MountCommits, self).tearDown()

    def git_repo(self):
        return dulwich.repo.Repo(self.repo_path)

    def test_temporary_commit(self):
        self.mount()

        git = self.git_repo()
        try:
            git.refs['refs/heads/mounted']
        except KeyError:
            self.fail('branch "mounted" does not exist')

        initial_heads = {
            "master": git.refs['refs/heads/master'],
            "mounted": git.refs['refs/heads/mounted'],
        }
        self.assertNotEqual(initial_heads['master'], initial_heads['mounted'])

        with open(path.join(self.mount_point, 'bigfile'), 'wb') as f:
            filesize = filesystem.WRITE_BUFFER_SIZE * 3
            for c in xrange(filesize / 4096 + 1):
                f.write('asdf' * 1024)

        git = self.git_repo()
        current_heads = {
            "master": git.refs['refs/heads/master'],
            "mounted": git.refs['refs/heads/mounted'],
        }
        self.assertEqual(initial_heads['master'], current_heads['master'])
        self.assertNotEqual(current_heads['master'], current_heads['mounted'])
        self.assertNotEqual(initial_heads['mounted'], current_heads['mounted'])

        self.umount()

        git = self.git_repo()
        final_heads = {
            "master": git.refs['refs/heads/master'],
        }
        self.assertRaises(KeyError, lambda: git.refs['refs/heads/mounted'])
        self.assertNotEqual(final_heads['master'], current_heads['master'])

    def test_no_modifications(self):
        self.mount()
        git = self.git_repo()
        initial_master = git.refs['refs/heads/master']

        self.umount()
        git = self.git_repo()
        final_master = git.refs['refs/heads/master']

        self.assertEqual(final_master, initial_master)
