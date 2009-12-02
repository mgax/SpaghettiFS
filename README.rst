SpaghettiFS
===========

SpaghettiFS is a FUSE filesystem that stores data in a Git repository.

Getting started
---------------
SpaghettiFS code is experimental, not suitable for anything important. It will
steal your files, crash your computer and burn down your house. Handle with
care. That being said, here's a quick guide:

 - clone the source code: ``git clone
   git://github.com/alex-morega/SpaghettiFS.git``
 - (optionally) set up a virtualenv
 - run ``python setup.py develop``
 - run unit tests: ``python setup.py test -q`` or ``python
   spaghettifs/tests/all.py``
 - create a blank filesystem: ``spaghettifs mkfs path/to/repo.sfs``
 - mount the filesystem: ``spaghettifs mount path/to/repo.sfs path/to/mount``

Missing features
----------------
 - file metadata: owner, permissions, create/modify/access times
 - symlinks, renaming of folders
 - fsck
