def import_obj(name):
    '''
    Import object by its absolute path
    (including the path inside the module, the one composed from attributes)
    '''
    parts = name.split('.')
    parts_copy = parts[:]
    while parts_copy:
        try:
            module = __import__('.'.join(parts_copy))
            break
        except ImportError:
            del parts_copy[-1]
            if not parts_copy:
                raise
    parts = parts[1:]
    obj = module
    for part in parts:
        obj = getattr(obj, part)
    return obj
