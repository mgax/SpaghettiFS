===========
SpaghettiFS
===========

SpaghettiFS is a FUSE filesystem that stores data in a Git repository.

Getting started
---------------
SpaghettiFS code is experimental, not suitable for anything important. It will
steal your files, crash your computer and burn down your house. Handle with
care. That being said, here's a quick guide:
 - clone the source code: ``git clone
   git://github.com/alex-morega/spaghettifs.git``
 - (optionally) set up a virtualenv
 - run ``python setup.py develop``
 - manually install fuse.py http://code.google.com/p/fusepy/ in your
   ``site-packages`` folder
 - run unit tests: ``python setup.py test -q`` or ``python
   spaghettifs/tests/all.py``
 - copy the test repository from ``spaghettifs/tests/repo.git`` to wherever
 - mount the test repository: ``spaghettifs path/to/repo.git path/to/mount``

There is currently no code to create an empty repository. Also, don't remove
every last file in a repository, or you won't be able to create any new files.
As I said, it's experimental. :)

Missing features
----------------
 - code to initialize a repository
 - hard links, symlinks
 - file metadata: owner, permissions, create/modify/access times
 - fsck

Performance issues
------------------
 - every single filesystem operation creates a commit (TODO: write buffering)
 - inodes, inode blocks and folder contents are stored as flat lists
