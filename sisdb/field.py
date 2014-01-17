###########################################################
# The information in this document is proprietary
# to VeriSign and the VeriSign Product Development.
# It may not be used, reproduced or disclosed without
# the written approval of the General Manager of
# VeriSign Product Development.
#
# PRIVILEGED AND CONFIDENTIAL
# VERISIGN PROPRIETARY INFORMATION
# REGISTRY SENSITIVE INFORMATION
#
# Copyright (c) 2013 VeriSign, Inc.  All rights reserved.
###########################################################

import schema
import datastructures

class SisFieldError(Exception):
    def __init__(self, value, *args, **kwargs):
        self.value = value

    def __str__(self):
        return repr(self.value)

class SisField(object):
    def __init__(self, field_descriptor, *args, **kwargs):
        self.field_desc = field_descriptor

    def __eq__(self, other):
        if isinstance(other, SisField):
            return other.field_desc == self.field_desc
        return False

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance._data.get(self.name, None)

    def __set__(self, instance, value):
        if (self.name not in instance._data or
            instance._data[self.name] != value):
                instance._mark_as_changed(self.name)
                instance._data[self.name] = value

    def to_sis_value(self, value):
        return value

    def raise_error(self, msg):
        raise SisFieldError(msg)


class BooleanField(SisField):
    def __init__(self, field_descriptor, *args, **kwargs):
        super(BooleanField, self).__init__(field_descriptor, *args, **kwargs)

    def to_sis_value(self, value):
        if value in (True, False):
            return bool(value)
        elif value in ('true', 'True'):
            return True
        elif value in ('false', 'False', None):
            return False
        self.raise_error("Cannot convert to Boolean")

class NumberField(SisField):
    def __init__(self, field_descriptor, *args, **kwargs):
        super(NumberField, self).__init__(field_descriptor, *args, **kwargs)

    def to_sis_value(self, value):
        if value is None:
            return value
        if type(value) in (int, float):
            return value

        try:
            return int(value)
        except (ValueError, TypeError):
            try:
                return float(value)
            except (ValueError, TypeError):
                self.raise_error("Cannot convert to Number")

class StringField(SisField):
    def __init__(self, field_descriptor, *args, **kwargs):
        super(StringField, self).__init__(field_descriptor, *args, **kwargs)

    def to_sis_value(self, value):
        if value is None:
            return value
        return str(value)

class MixedField(SisField):
    def __init__(self, field_descriptor, *args, **kwargs):
        super(MixedField, self).__init__(field_descriptor, *args, **kwargs)

    def __get__(self, instance, owner):
        if instance is None:
            return self
        mix = instance._data.get(self.name, None)
        if not mix or not isinstance(mix, dict):
            instance._data[self.name] = datastructures.BaseDict({}, instance, self.name)
        elif not isinstance(mix, datastructures.BaseDict):
            instance._data[self.name] = datastructures.BaseDict(mix, instance, self.name)

        return instance._data[self.name]

    def __set__(self, instance, value):
        if (self.name not in instance._data or
            instance._data[self.name] != value):
                instance._mark_as_changed(self.name)
                instance._data[self.name] = value

class ListField(SisField):
    def __init__(self, field_descriptor, *args, **kwargs):
        super(ListField, self).__init__(field_descriptor, *args, **kwargs)
        self._field_cls = kwargs.get('field_cls')

    def __get__(self, instance, owner):
        if instance is None:
            return self
        vals = instance._data.get(self.name, None)
        if not vals or not isinstance(vals, list):
            instance._data[self.name] = datastructures.BaseList([], instance, self.name)
        elif not isinstance(vals, datastructures.BaseList):
            instance._data[self.name] = datastructures.BaseList(vals, instance, self.name)

        return instance._data[self.name]

    def __set__(self, instance, value):
        if (self.name not in instance._data or
            instance._data[self.name] != value):
                instance._mark_as_changed(self.name)
                instance._data[self.name] = self._list

class ObjectIdField(SisField):
    def __init__(self, field_descriptor, *args, **kwargs):
        super(ObjectIdField, self).__init__(field_descriptor, *args, **kwargs)

    def to_sis_value(self, value):
        if type(value) == dict:
            # sub doc - if inner _id isn't there, fail
            if value.get('_id', None):
                self.raise_error("Cannot convert to ObjectId")
            return str(value.get('_id'))

        return str(value)

class EmbeddedSchemaField(SisField):
    def __init__(self, schema_desc, *args, **kwargs):
        super(EmbeddedSchemaField, self).__init__(schema_desc, *args, **kwargs)
        schema_desc = schema_desc
        sisdb = kwargs.get('sisdb')
        e_name = kwargs.get('e_name')
        self.schema_cls = schema.create_embedded_schema(sisdb, schema_desc, e_name)

    def __get__(self, instance, owner):
        if instance is None:
            return self

        vals = instance._data.get(self.name, None)
        if not vals:
            vals = self.schema_cls(instance, self.name)
            instance._data[self.name] = vals
        else:
            if not isinstance(vals, self.schema_cls):
                # don't mark as changed.
                vals_dict = vals
                vals = self.schema_cls(instance, self.name)
                vals.set_data(vals_dict)

        return vals

    def __set__(self, instance, value):
        if (self.name not in instance._data or
            instance._data[self.name] != value):
                instance._mark_as_changed(self.name)
                instance._data[self.name] = value


def create_field_from_string(descriptor, name, sisdb):
    field_types = {
        'number' : NumberField,
        'boolean' : BooleanField,
        'string' : StringField,
        'objectid' : ObjectIdField,
        'ipaddress' : MixedField,
        'mixed' : MixedField
    }

    if (type(descriptor) == unicode or
        type(descriptor) == str):
        stype = str(descriptor).lower()
        if stype not in field_types:
            raise SisFieldError('Unknown type: %s', descriptor)

        result = field_types[stype]({ 'type' : stype })
        result.name = name
        return result

    return None


def create_field(descriptor, name, sisdb, schema_name):
    result = create_field_from_string(descriptor, name, sisdb)

    if result:
        return result

    # embedded document
    if type(descriptor) == dict:
        # could be a proper descriptor with a type
        e_name = '__'.join([schema_name, name])
        desc_type = descriptor.get('type', None)
        if not desc_type:
            # it's a mixed object or inner schema
            if len(descriptor.keys()) == 0:
                # mixed
                result = MixedField(descriptor)
            else:
                # embedded schema
                result = EmbeddedSchemaField(descriptor, sisdb=sisdb, e_name=e_name)
        else:
            # type.. is it a string or an object
            result = create_field_from_string(desc_type, name, sisdb)
            if result:
                return result
            # type is an object or list so it's an embedded schema
            result = EmbeddedSchemaField(desc_type, sisdb=sisdb, e_name=e_name)

    # array
    elif type(descriptor) == list:
        result = ListField(descriptor, field_cls=None)

    if not result:
        raise SisFieldError("Unknown type: %s" % str(descriptor))

    result.name = name
    return result

