"""
TreeTree is a wrapper over `easygit.EasyTree` that provides more efficient
storage of lists. Keys must be strings made up of digits, and they should
be as close as possible to the indices of a list.
"""

class TreeTree(object):
    def __init__(self, container):
        self.container = container

    def locate(self, name, create=None):
        check_name(name)

        def traverse(node, name, create=None):
            try:
                return node[name]
            except KeyError:
                if create is None:
                    raise
                elif create == 'tree':
                    return node.new_tree(name)
                elif create == 'blob':
                    return node.new_blob(name)
                else:
                    raise NotImplementedError

        node = traverse(self.container, 'tt%d' % len(name), create='tree')
        for digit in name[:-1]:
            node = traverse(node, digit, create='tree')
        if create is not None and name[-1] in node:
            raise ValueError('entry %r already exists' % name)
        return traverse(node, name[-1], create=create)

    def new_tree(self, name):
        return self.locate(name, create='tree')

    def new_blob(self, name):
        return self.locate(name, create='blob')

    def __getitem__(self, name):
        return self.locate(name)

def check_name(name):
    if not name:
        raise ValueError
    if not isinstance(name, basestring):
        raise ValueError
    for item in name:
        if item not in '0123456789':
            raise ValueError
