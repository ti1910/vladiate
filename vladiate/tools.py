import lark
from .validators import TYPE_TO_VALIDATOR

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
            if attr.get('attribute'):
                for prop in attr['attribute']:
                    if prop.get('variable'):
                        name = None
                        _type = None
                        for i in prop['variable']:
                            if i.get('var'):
                                name = i['var'][0]
                            if i.get('type'):
                                _type = i['type'][0]
                        if not name or not _type:
                            print((name, _type))
                        else:
                            res[class_name][name] = TYPE_TO_VALIDATOR[_type]
    return res
