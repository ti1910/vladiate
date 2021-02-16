import re
from uuid import UUID
import datetime
from itertools import islice
from math import log

from vladiate.exceptions import ValidationException, BadValidatorException

def COMB(*validators):
    def wrap(*args, **kwargs):
        for v in validators:
            v(*args, **kwargs)
    return wrap

class Validator(object):
    """ Generic Validator class """

    def __init__(self, empty_ok=False, meta=None, **kwargs):
        self.fail_count = 0
        self.empty_ok = empty_ok
        self.meta = meta

    @property
    def bad(self):
        """ Return something containing the "bad" fields """
        raise NotImplementedError

    def validate(self, field, row):
        """ Validate the given field. Also is given the row context """
        raise NotImplementedError


class CastValidator(Validator):
    """ Validates that a field can be cast to a float """

    def __init__(self, **kwargs):
        super(CastValidator, self).__init__(**kwargs)
        self.invalid_set = set([])

    def validate(self, field, row={}):
        try:
            if field or not self.empty_ok:
                self.cast(field)
        except ValueError as e:
            self.invalid_set.add(field)
            raise ValidationException(e)

    @property
    def bad(self):
        return self.invalid_set


class FloatValidator(CastValidator):
    """ Validates that a field can be cast to a float """

    def __init__(self, **kwargs):
        super(FloatValidator, self).__init__(**kwargs)
        self.cast = float


class IntValidator(CastValidator):
    """ Validates that a field can be cast to an int """
    size = 4

    @staticmethod
    def bytes_needed(n):
        n = abs(int(n)) * 2
        if n == 0:
            return 1
        return int(log(n, 256)) + 1 #TODO byte shift?

    def cast(self, a):
        assert self.bytes_needed(a) <= self.size

class HexValidator(CastValidator):
    def __init__(self, **kwargs):
        super(HexValidator, self).__init__(**kwargs)
        self.cast = lambda i: int(i, 16)

class BigIntValidator(IntValidator):
    """ Validates that a field can be cast to an bigint """
    size = 8

class SmallIntValidator(IntValidator):
    """ Validates that a field can be cast to an smallint """
    size = 2

class TinyIntValidator(IntValidator):
    """ Validates that a field can be cast to an tinyint """
    size = 1

class StrValidator(CastValidator):
    """ Validates that a field can be cast to an str """

    def __init__(self, **kwargs):
        super(StrValidator, self).__init__(**kwargs)
        self.cast = str

class LenValidator(CastValidator):
    """ Validates that a field can be cast to an str with predefined max length"""

    def __init__(self, options, **kwargs):
        super(LenValidator, self).__init__(**kwargs)
        assert len(options) == 1
        self.max_len = int(list(options)[0])

    def cast(self, string):
        if len(str(string)) > self.max_len:
            raise ValueError("String is too long!")

class DateValidator(CastValidator):
    """ Validates that a field can be cast to an str """

    def __init__(self, **kwargs):
        super(DateValidator, self).__init__(**kwargs)
        self.cast = lambda v: datetime.datetime.strptime(v, "%Y-%m-%dT")

class TimestampValidator(CastValidator):
    """ Validates that a field can be cast to an str """

    def __init__(self, **kwargs):
        super(TimestampValidator, self).__init__(**kwargs)
        self.cast = lambda v: datetime.datetime.strptime(v, "%Y-%m-%dT%H:%M:%S.%fZ")

class UUIDValidator(CastValidator):
    """ Validates that a field can be cast to an str """

    def __init__(self, **kwargs):
        super(UUIDValidator, self).__init__(**kwargs)
        self.cast = UUID

class SetValidator(Validator):
    """ Validates that a field is in the given set """

    def __init__(self, options=[], **kwargs):
        super(SetValidator, self).__init__(**kwargs)
        self.options = set(options)
        self.invalid_set = set([])
        if self.empty_ok:
            self.options.add("")

    def validate(self, field, row={}):
        if field not in self.options:
            self.invalid_set.add(field)
            raise ValidationException(
                "'{}' is not in {}".format(field, _stringify_set(self.options, 100))
            )

    @property
    def bad(self):
        return self.invalid_set


class UniqueValidator(Validator):
    """ Validates that a field is unique within the file """

    def __init__(self, unique_with=[], **kwargs):
        super(UniqueValidator, self).__init__(**kwargs)
        self.unique_values = set([])
        self.duplicates = set([])
        self.unique_with = unique_with
        self.unique_check = False

    def _precheck_unique_with(self, row):
        extra = set(self.unique_with) - set(row.keys())
        if extra:
            raise BadValidatorException(extra)
        self.unique_check = True

    def validate(self, field, row={}):
        if field == "" and self.empty_ok:
            return
        if self.unique_with and not self.unique_check:
            self._precheck_unique_with(row)

        key = tuple([field] + [row[k] for k in self.unique_with])
        if key not in self.unique_values:
            self.unique_values.add(key)
        else:
            self.duplicates.add(key)
            if self.unique_with:
                raise ValidationException(
                    "'{}' is already in the column (unique with: {})".format(
                        field, key[1:]
                    )
                )
            else:
                raise ValidationException("'{}' is already in the column".format(field))

    @property
    def bad(self):
        return self.duplicates


class RegexValidator(Validator):
    """ Validates that a field matches a given regex """

    def __init__(self, pattern=r"di^", full=False, **kwargs):
        super(RegexValidator, self).__init__(**kwargs)
        self.failures = set([])
        if full:
            self.regex = re.compile(r"(?:" + pattern + r")\Z")
        else:
            self.regex = re.compile(pattern)

    def validate(self, field, row={}):
        if not self.regex.match(field) and (field or not self.empty_ok):
            self.failures.add(field)
            raise ValidationException(
                "'{}' does not match pattern /{}/".format(field, self.regex)
            )

    @property
    def bad(self):
        return self.failures


class RangeValidator(Validator):
    def __init__(self, low, high, **kwargs):
        super(RangeValidator, self).__init__(**kwargs)
        self.fail_count = 0
        self.low = low
        self.high = high
        self.outside = set()

    def validate(self, field, row={}):
        if field == "" and self.empty_ok:
            return
        try:
            value = float(field)
            if not self.low <= value <= self.high:
                raise ValueError
        except ValueError:
            self.outside.add(field)
            raise ValidationException(
                "'{}' is not in range {} to {}".format(field, self.low, self.high)
            )

    @property
    def bad(self):
        return self.outside


class EmptyValidator(Validator):
    """ Validates that a field is always empty """

    def __init__(self, **kwargs):
        super(EmptyValidator, self).__init__(**kwargs)
        self.nonempty = set([])

    def validate(self, field, row={}):
        if field != "":
            self.nonempty.add(field)
            raise ValidationException("'{}' is not an empty string".format(field))

    @property
    def bad(self):
        return self.nonempty


class NotEmptyValidator(Validator):
    """ Validates that a field is not empty """

    def __init__(self, **kwargs):
        super(NotEmptyValidator, self).__init__(**kwargs)
        self.fail_count = 0
        self.failed = False

    def validate(self, field, row={}):
        if field == "":
            self.failed = True
            raise ValidationException("Row has empty field in column")

    @property
    def bad(self):
        return self.failed


class Ignore(Validator):
    """ Ignore a given field. Never fails """
    def __init__(self, **kwargs):
        super(Ignore, self).__init__(**kwargs)

    def validate(self, field, row={}):
        pass

    @property
    def bad(self):
        pass


class JsonSetValidator(Validator):
    """ JsonSetValidator a given field. Never fails """
    def __init__(self, **kwargs):
        super(JsonSetValidator, self).__init__(**kwargs)

    def validate(self, field, row={}):
        pass

    @property
    def bad(self):
        pass

class JsonValidator(Validator):
    """ JsonSetValidator a given field. Never fails """
    def __init__(self, **kwargs):
        super(JsonSetValidator, self).__init__(**kwargs)

    def validate(self, field, row={}):
        pass

    @property
    def bad(self):
        pass

class JsonListValidator(Validator):
    """ JsonListValidator a given field. Never fails """
    def __init__(self, **kwargs):
        super(JsonListValidator, self).__init__(**kwargs)

    def validate(self, field, row={}):
        pass

    @property
    def bad(self):
        pass

class NullValidator(Validator):
    """ NullValidator a given field. Never fails """
    def __init__(self, **kwargs):
        super(NullValidator, self).__init__(**kwargs)

    def validate(self, field, row={}):
        pass

    @property
    def bad(self):
        pass

def _stringify_set(a_set, max_len, max_sort_size=8192):
    """ Stringify `max_len` elements of `a_set` and count the remainings

    Small sets (len(a_set) <= max_sort_size) are displayed sorted.
    Large sets won't be sorted for performance reasons.
    This may result in an arbitrary ordering in the returned string.
    """
    # Don't convert `a_set` to a list for performance reasons
    text = "{{{}}}".format(
        ", ".join(
            "'{}'".format(value)
            for value in islice(
                sorted(a_set) if len(a_set) <= max_sort_size else a_set, max_len
            )
        )
    )
    if len(a_set) > max_len:
        text += " ({} more suppressed)".format(len(a_set) - max_len)
    return text

SPARK_TYPE_TO_VALIDATOR = {
        'string': StrValidator,
        'tinyint': TinyIntValidator,
        'smallint': SmallIntValidator,
        'int': IntValidator,
        'bigint': BigIntValidator,
        'timestamp': TimestampValidator,
        'date': DateValidator,
        'float': FloatValidator, #TODO 4 bytes conversion
        'double': FloatValidator,
        }

TYPE_TO_VALIDATOR = {
        'deident': IntValidator, #TODO
        'from': IntValidator, #TODO
        'tenant_id': IntValidator, #TODO
        'softdelete': StrValidator, #TODO
        #'created_at': COMB(TimestampValidator, NotEmptyValidator),
        'created_at': TimestampValidator,
        'len': LenValidator,
        'key': UUIDValidator,

        'nodwh': Ignore,
        'nostaging': Ignore,
        'nocompare': Ignore,
        'deprecated': Ignore,
        'size': Ignore,
        'mode': Ignore,
        'changes': Ignore,
        'deletion': Ignore,
#        }
#CONTENT_TO_VALIDATOR = {
        'set': SetValidator,
        'uuid': UUIDValidator,
        'decimal': IntValidator,
        'hex': HexValidator,
        'float': FloatValidator,
        'json': JsonValidator, #TODO
        'str': StrValidator,
        'regexp': SetValidator, #TODO
        'null': NullValidator, #TODO

        'json_set': JsonSetValidator, #json array of items. Item order is not important.
        'json_list': JsonListValidator,        #json array of items. Item order is important.
        'set': SetValidator,          #Order is NOT important.
        'list': SetValidator,         #Order is important.
        }
