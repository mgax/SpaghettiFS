import sys
import logging
from optparse import OptionParser

from spaghettifs.filesystem import mount

parser = OptionParser()
parser.add_option("-v", "--verbose",
                  action="store_const", const=logging.DEBUG, dest="loglevel")
parser.add_option("-q", "--quiet",
                  action="store_const", const=logging.ERROR, dest="loglevel")
parser.set_defaults(loglevel=logging.INFO)

def main():
    options, args = parser.parse_args()
    repo_path, mount_path = args

    print "mounting %r at %r" % (repo_path, mount_path)
    mount(repo_path, mount_path, loglevel=options.loglevel)

if __name__ == '__main__':
    main()
