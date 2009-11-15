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
 - create a blank filesystem: ``spaghettifs mkfs path/to/repo.sfs``
 - mount the filesystem: ``spaghettifs mount path/to/repo.sfs path/to/mount``

Missing features
----------------
 - hard links, renaming files/folders, symlinks
 - file metadata: owner, permissions, create/modify/access times
 - fsck

Performance issues
------------------
 - inodes, inode blocks and folder contents are stored as flat lists
 - inode blocks are 64KB in size, which generates a lot of git objects
