"""
TreeTree is a wrapper over `easygit.EasyTree` that provides more efficient
storage of lists. Keys must be strings made up of digits, and they should
be as close as possible to the indices of a list.
"""

class TreeTree(object):
    def __init__(self, container, prefix='tt'):
        self.container = container
        self.prefix = prefix

    def walk(self, name, look):
        check_name(name)
        keys = ['%s%d' % (self.prefix, len(name))] + list(name)
        last_key = keys.pop()
        ikeys = iter(keys)
        def step(node):
            assert node.is_tree
            try:
                key = next(ikeys)
            except StopIteration:
                return look(node, last_key, True, lambda nextnode: nextnode)
            else:
                return look(node, key, False, step)
        return step(self.container)

    def new_tree(self, name):
        def look(node, key, last, step):
            try:
                nextnode = node[key]
            except KeyError:
                nextnode = node.new_tree(key)
            return step(nextnode)

        value = self.walk(name, look)
        if not value.is_tree:
            raise ValueError
        return value

    def new_blob(self, name):
        def look(node, key, last, step):
            try:
                nextnode = node[key]
            except KeyError:
                if last:
                    nextnode = node.new_blob(key)
                else:
                    nextnode = node.new_tree(key)
            return step(nextnode)

        value = self.walk(name, look)
        if value.is_tree:
            raise ValueError
        return value

    def clone(self, source, name):
        def look(node, key, last, step):
            try:
                nextnode = node[key]
            except KeyError:
                if last:
                    nextnode = node.clone(source, key)
                else:
                    nextnode = node.new_tree(key)
            return step(nextnode)

        value = self.walk(name, look)
        if source.is_tree and not value.is_tree:
            raise ValueError
        if not source.is_tree and value.is_tree:
            raise ValueError
        return value

    def __getitem__(self, name):
        def look(node, key, last, step):
            return step(node[key])

        return self.walk(name, look)

    def __contains__(self, name):
        try:
            self[name]
        except KeyError:
            return False
        else:
            return True

    def __delitem__(self, name):
        def look(node, key, last, step):
            if last:
                del node[key]
                return

            nextnode = node[key]
            step(nextnode)
            if not nextnode.keys():
                del node[key]

        return self.walk(name, look)

def check_name(name):
    if not name:
        raise ValueError('Blank names not allowed: %r' % name)
    if not isinstance(name, basestring):
        raise ValueError('Names must be strings: %r' % name)
    for item in name:
        if item not in '0123456789':
            raise ValueError('Names must contain only digits: %r' % name)
