SpaghettiFS is a FUSE filesystem that stores data in a Git repository.

Missing features:
 - code to initialize a repository
 - hard links, symlinks
 - file metadata: owner, permissions, create/modify/access times
 - fsck

Performance issues:
 - every single filesystem operation creates a commit (TODO: write buffering)
 - inodes, inode blocks and folder contents are stored as flat lists
