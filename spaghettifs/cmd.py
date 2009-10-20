import sys
import logging
from optparse import OptionParser

from spaghettifs.storage import GitStorage
from spaghettifs.filesystem import mount

usage = "usage: %prog <mkfs REPO_PATH | mount REPO_PATH MOUNT_PATH [options]>"
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
        GitStorage.create(args[1])

    elif args[0] == 'mount':
        if len(args) != 3:
            return parser.print_usage()
        repo_path, mount_path = args[1:]
        print "mounting %r at %r" % (repo_path, mount_path)
        mount(repo_path, mount_path, loglevel=options.loglevel)

    else:
        return parser.print_usage()

if __name__ == '__main__':
    main()
