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

class Validator:
    def __init__(self, name, options=()):
        assert (name in TYPE_TO_VALIDATOR) or (name in SPARK_TYPE_TO_VALIDATOR), name
        self.name = name
        self.options = options
        if name in TYPE_TO_VALIDATOR:
            if self.options:
                self.__validator = TYPE_TO_VALIDATOR[self.name](options=self.options)
            else:
                self.__validator = TYPE_TO_VALIDATOR[self.name]()
        else:
            self.__validator = SPARK_TYPE_TO_VALIDATOR[self.name]()

    def get(self):
        return self.__validator

class Attribute:
    def __init__(self, name, options=()):
        assert name in TYPE_TO_VALIDATOR, name
        self.name = name
        self.options = options

class Column:
    def __init__(self, name, _type, validators, visibility):
        assert name and _type
        self.name = name
        self.type = _type
        self.validators = validators
        self.visibility = visibility

def __parse_validator(_dict):
    attribute = None
    options = []
    for c in _dict:
        if c.get('attribute'):
            attribute = list(c.get('attribute')[0].keys())[0]
        elif c.get('option'):
            options.extend(c.get('option'))
    if not attribute:
        raise Exception('Faled to get attribute!')
    return Validator(attribute, options)

def __parse_ent_attrattribute(_dict):
    attribute = None
    options = []
    for c in _dict:
        if c.get('attribute'):
            attribute = list(c.get('attribute')[0].keys())[0]
        elif c.get('option'):
            options.extend(c.get('option'))
    if not attribute:
        raise Exception('Faled to get attribute!')
    return Attribute(attribute, options)

def __parse_column(_dict):
    name = None
    _type = None
    validators = []
    options = []
    public = None
    visibility = None
    for prop in _dict:
        if prop.get('name'):
            name = prop['name'][0]
        elif prop.get('type'):
            _type = list(prop['type'][0].keys())[0]
            validators.append(Validator(_type))
        elif prop.get('validator'):
            validators.append(__parse_validator(prop.get('validator')))
        elif prop.get('visibility'):
            visibility = list(prop.get('visibility')[0].keys())[0]
    return Column(name, _type, [v.get() for v in validators], visibility)

def simplify(_dict):
    res = {}
    ent_attr = {}
    schema = {}

    for c in _dict['start']:
        class_name = ''
        content = c.get('ent_attr')
        if not content:
            continue
        for attr in content:
            if attr.get('class_name'):
                class_name = attr['class_name'][0]
                if not ent_attr.get(class_name):
                    ent_attr[class_name] = {}
        assert class_name
        for attr in content:
            if not attr.get('validator'):
                continue
            attribute = __parse_ent_attrattribute(attr['validator'])
            ent_attr[class_name][attribute.name] = attribute.options

    for c in _dict['start']:
        class_name = ''
        content = c.get('class')
        if not content:
            continue
        for attr in content:
            if attr.get('class_name'):
                class_name = attr['class_name'][0]
                if not res.get(class_name):
                    res[class_name] = {}
                if not schema.get(class_name):
                    schema[class_name] = {}
        assert class_name
        for attr in content:
            if c.get('class') and attr.get('column'):
                column = __parse_column(attr.get('column'))
                res[class_name][column.name] = column.validators
                schema[class_name][column.name] = column.type
    return res, schema
