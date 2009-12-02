import sys
import logging
from optparse import OptionParser

from spaghettifs import storage
from spaghettifs import filesystem

usage = """\
usage: %prog mkfs REPO_PATH
       %prog mount REPO_PATH MOUNT_PATH [options]
       %prog fsck REPO_PATH
       %prog upgrade REPO_PATH
""".strip()

parser = OptionParser(usage=usage)
parser.add_option("-v", "--verbose",
                  action="store_const", const=logging.DEBUG, dest="loglevel")
parser.add_option("-q", "--quiet",
                  action="store_const", const=logging.ERROR, dest="loglevel")
parser.set_defaults(loglevel=logging.INFO)

def main():
    options, args = parser.parse_args()

    if not args:
        return parser.print_usage()

    elif args[0] == 'mkfs':
        if len(args) != 2:
            return parser.print_usage()
        storage.GitStorage.create(args[1])

    elif args[0] == 'mount':
        if len(args) != 3:
            return parser.print_usage()
        repo_path, mount_path = args[1:]
        print "mounting %r at %r" % (repo_path, mount_path)
        filesystem.mount(repo_path, mount_path, loglevel=options.loglevel)

    elif args[0] == 'fsck':
        if len(args) != 2:
            return parser.print_usage()
        storage.fsck(args[1], sys.stdout)

    elif args[0] == 'upgrade':
        if len(args) != 2:
            return parser.print_usage()
        handler = logging.StreamHandler()
        handler.setLevel(options.loglevel)
        logging.getLogger('spaghettifs.storage.upgrade').addHandler(handler)
        storage.convert_fs_to_treetree_inodes(args[1])

    else:
        return parser.print_usage()

if __name__ == '__main__':
    main()
