import lark
from .validators import TYPE_TO_VALIDATOR, SPARK_TYPE_TO_VALIDATOR

def tree_to_dict(item, res):
    if isinstance(item, lark.Tree):
        res[item.data] = []
        for child in item.children:
            if isinstance(child, lark.Tree):
                new_tree = {}
                tree_to_dict(child, new_tree)
                res[item.data].append(new_tree)
            if isinstance(child, lark.Token):
                res[item.data].append(str(child))
    else:
        assert False, item  # fall-through

def simplify(_dict):
    res = {}
    for c in _dict['start']:
        class_name = ''
        if not c.get('class'):
            continue
        for attr in c.get('class'):
            if attr.get('class_name'):
                res[attr['class_name'][0]] = {}
                class_name = attr['class_name'][0]
        assert class_name
        for attr in c.get('class'):
            if attr.get('column'):
                name = None
                _type = None
                validator = None
                options = []
                public = False
                for prop in attr['column']:
                    if prop.get('name'):
                        name = prop['name'][0]
                    elif prop.get('type'):
                        _type = prop['type'][0]
                    elif prop.get('options'):
                        options = set(d['option'][0] for d in prop['options'])
                    elif prop.get('validator'):
                        validator = prop['validator'][0]
                    elif 'public' in prop.keys():
                        public = True
                if not name or not _type:
                    raise Exception(repr(name, _type))
                if not public:
                    continue
                res[class_name][name] = [SPARK_TYPE_TO_VALIDATOR[_type]()]
                if validator:
                    if options:
                        res[class_name][name].append(TYPE_TO_VALIDATOR[validator](valid_set=options))
                    else:
                        res[class_name][name].append(TYPE_TO_VALIDATOR[validator]())
    return res
