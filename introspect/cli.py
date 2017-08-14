'''
Usage:
    introspect --database=DATABASE

Options:
    DATABASE  path to pony.orm.Database
'''

from collections import defaultdict

from pony.utils import cached_property

import keyword
import re
from collections import OrderedDict

from .utils import import_obj

from docopt import docopt

from pony.orm import Database

import os
from textwrap import dedent

import warnings

from .postgres import Introspection

# TODO related field set

class Command:
    help = "Introspects the database tables in the given database and outputs a Django model module."


    KWARGS_ORDER = dedent('''\
        unique nullable default db_column
        ''').split()

    @cached_property
    def imports(self):
        return [
            'from pony.orm import *'
        ]
    
    def get_output(self):
        lines = list(self._get_output())
        yield "# This is an auto-generated module with pony entities."
        yield "# Feel free to rename the models, but don't rename _table_ or field names."
        yield ''
        yield from set(self.imports)
        yield ''
        yield from lines

    def table2model(self, table_name):
        return re.sub(r'[^a-zA-Z0-9]', '', table_name.title())

    def is_pony_table(self, table):
        return table in ['migration', 'pony_version']

    @cached_property
    def field_counters(self):
        return defaultdict(int)

    @cached_property
    def relations_counters(self):
        return defaultdict(int)

    def _make_introspection(self):
        options = docopt(__doc__)
        database = options['--database']
        db = import_obj(database)

        connection = db.provider.connect()

        # get provider
        if isinstance(db, Database):
            introspection = Introspection(connection, provider=db.provider)
        else:
            raise NotImplementedError

        self.introspection = introspection

        ret = {}

        with connection.cursor() as cursor:
            tables_to_introspect = introspection.table_names(cursor)

            counters = self.field_counters
            rel_counters = self.relations_counters

            for table_name in tables_to_introspect:
                try:
                    relations = introspection.get_relations(cursor, table_name)
                except NotImplementedError:
                    if os.environ.get('DEBUG'):
                        raise
                    relations = {}
                try:
                    constraints = introspection.get_constraints(cursor, table_name)
                except NotImplementedError:
                    if os.environ.get('DEBUG'):
                        raise
                    constraints = {}
                primary_key_columns = list(
                    introspection.get_primary_key_columns(cursor, table_name)
                )
                unique_columns = [
                    c['columns'][0] for c in constraints.values()
                    if c['unique'] and len(c['columns']) == 1
                ]
                table_description = introspection.get_table_description(cursor, table_name)
                
                if self.is_pony_table(table_name):
                    continue
                # normalize field names & increment field name counters
                for field in table_description:
                    if field.name in relations:
                        continue
                    field_name = field.name
                    field.name, _, _ = self.normalize_col_name(field_name)

                    field.name = f"{field.name}{counters[(table_name, field.name)] or ''}"
                    counters[(table_name, field.name)] += 1

                # check if it's an m2m table
                related_tables = []
                is_m2m = False
                for field in table_description:
                    if field.name in primary_key_columns:
                        continue
                    #relations: {'a_id': ('id', 'm2m_a')}
                    if field.name not in relations:
                        break
                    tblname = relations[field.name][1]
                    related_tables.append({'table': tblname, 'field': field.name})
                else:
                    
                    is_m2m = len(set(t['table'] for t in related_tables)) == 2

                if is_m2m:
                    # store the relation in the each of related tables
                    this, other = related_tables
                    this_field, other_field = this['field'], other['field']
                    this['field'] = f"{this['field']}_set{counters[(other['table'], this['field'])] or ''}"
                    other['field'] = f"{other['field']}_set{counters[(this['table'], other['field'])] or ''}"
                    counters[(this['table'], other_field)] += 1
                    counters[(other['table'], this_field)] += 1
                    for this, other in ((this, other), (other, this)):
                        ret.setdefault(this['table'], {}).setdefault('rel_attrs', []).append({
                            'name': other['field'],
                            'table': other['table'],
                            'cls': 'Set',
                            'reverse': this['field']
                        })
                        rel_counters[(this['table'], other['table'])] += 1
                    continue

                # calculate relation attributes
                for column_name, (_attr, ref_table) in relations.items():
                    att_name, *_ = self.normalize_col_name(column_name)
                    index = counters[(table_name, att_name)]
                    counters[(table_name, att_name)] += 1
                    att_name = f"{att_name}{index or ''}"
                    rel_attrs = ret.setdefault(table_name, {}).setdefault('rel_attrs', [])
                    # getting reverse name             
                    reverse = table_name.lower()
                    index = counters[(ref_table, reverse)]
                    counters[(ref_table, reverse)] += 1
                    reverse = f"{reverse}_set{index or ''}"

                    rel_attrs.append({
                        'name': att_name,
                        'cls': 'Required',
                        'reverse': reverse,
                        'table': ref_table,
                    })
                    rel_counters[(table_name, ref_table)] += 1
                    rel_attrs = ret.setdefault(ref_table, {}).setdefault('rel_attrs', [])
                    rel_attrs.append({
                        'name': reverse,
                        'cls': 'Set',
                        'reverse': att_name,
                        'table': table_name,
                    })
                    rel_counters[(ref_table, table_name)] += 1

                ret.setdefault(table_name, {}).update({
                    'relations': relations, 'description': table_description,
                    'unique_columns': unique_columns, 'primary_key_columns': primary_key_columns,
                    'constraints': constraints,
                })
                
            return ret

    def _get_output(self):
        # not requires connection?
        all_data = self._make_introspection()
        table2model = self.table2model

        yield 'db = Database()'
        known_models = []

        for table_name, data in all_data.items():
            relations = data['relations']
            primary_key_columns = data['primary_key_columns']
            unique_columns = data['unique_columns']
            table_description = data['description']

            yield ''
            yield ''
            model_name = table2model(table_name)
            yield f'class {model_name}(db.Entity):'
            yield f'    _table_ = "{table_name}"'
            known_models.append(model_name)
            # used_column_names = []  # Holds column names used in the table so far
            column_to_field_name = {}  # Maps column names to names of model fields

            for row in table_description:
                comment_notes = []  # Holds Field notes, to be displayed in a Python comment.
                extra_params = OrderedDict()  # Holds Field parameters such as 'db_column'.
                column_name = att_name = row[0]

                # used_column_names.append(att_name)
                column_to_field_name[column_name] = att_name
                field_kwargs = {}

                # Add primary_key and unique, if necessary.
                if [column_name] == primary_key_columns:
                    extra_params['primary_key'] = True
                elif column_name in unique_columns:
                    field_kwargs['unique'] = True

                is_relation = column_name in relations
                if not is_relation:
                    # Calling `get_field_type` to get the field type string and any
                    # additional parameters and notes.
                    field_type, field_params, field_notes = self.get_field_type(#connection,
                            table_name, row)
                    extra_params.update(field_params)
                    field_kwargs.update(field_params)
                    comment_notes.extend(field_notes)

                if att_name == 'id' and extra_params == {'primary_key': True}:
                    if field_type == 'AUTO':
                        continue

                if row[6]:  # If it's NULL...
                    extra_params['null'] = True
                
                def sort_key(item, default=len(field_kwargs)):
                    key, val = item
                    try:
                        index = self.KWARGS_ORDER.index(key)
                    except ValueError:
                        return default
                    return index

                sorted_kwargs = sorted(field_kwargs.items(), key=sort_key)

                format_val = repr

                kwargs_list = [
                    f'{key}={format_val(val)}'
                    for key, val in sorted_kwargs
                ]
                kwargs_list = ', '.join(kwargs_list)
                if kwargs_list:
                    kwargs_list = f', {kwargs_list}'

                if not is_relation:
                    if extra_params.get('primary_key'):
                        cls = 'PrimaryKey'
                    elif extra_params.get('null'):
                        cls = 'Optional'
                    else:
                        cls = 'Required'
                    field_desc = f'{att_name} = {cls}({field_type}{kwargs_list})'

                    if comment_notes:
                        field_desc += f'  # {join(comment_notes)}'
                    yield f'    {field_desc}' 

            rel_attrs = data.get('rel_attrs', ())
            for attr in rel_attrs:
                model = self.table2model(attr['table'])
                reverse = ''
                if self.relations_counters[(table_name, attr['table'])] > 1:
                    reverse = f''', reverse="{attr['reverse']}"'''
                yield f'''    {attr['name']} = {attr['cls']}("{model}"{reverse})'''
            
            # compound primary key
            if len(primary_key_columns) > 1:
                attrs = [
                    column_to_field_name[c] for c in primary_key_columns
                ]
                yield f"    PrimaryKey({', '.join(attrs)})"


    def normalize_col_name(self, col_name):
        """
        Modify the column name to make it Python-compatible as a field name
        """
        field_params = {}
        field_notes = []

        new_name = col_name.lower()
        if new_name != col_name:
            field_notes.append('Field name made lowercase.')

        new_name, num_repl = re.subn(r'\W', '_', new_name)
        if num_repl > 0:
            field_notes.append('Field renamed to remove unsuitable characters.')

        if new_name.startswith('_'):
            new_name = 'attr%s' % new_name
            field_notes.append("Field renamed because it started with '_'.")

        if new_name.endswith('_'):
            new_name = '%sattr' % new_name
            field_notes.append("Field renamed because it ended with '_'.")

        if keyword.iskeyword(new_name):
            new_name += '_attr'
            field_notes.append('Field renamed because it was a Python reserved word.')

        if new_name[0].isdigit():
            new_name = 'number_%s' % new_name
            field_notes.append("Field renamed because it wasn't a valid Python identifier.")

        if col_name != new_name:
            field_params['db_column'] = col_name

        return new_name, field_params, field_notes

    def get_field_type(self, table_name, row):
        """
        Given the database connection, the table name, and the cursor row
        description, this routine will return the given field type name, as
        well as any additional keyword parameters and notes for the field.
        """
        field_params = OrderedDict()
        field_notes = []

        try:
            field_type, _import = self.introspection.get_field_type(row[1], row)
        except KeyError:
            field_type = 'LongStr'
            _import = 'from pony.orm.ormtypes import LongStr'
            field_notes.append('This field type is a guess.')

        if _import:
            self.imports.append(_import)

        # This is a hook for data_types_reverse to return a tuple of
        # (field_type, field_params_dict).
        if type(field_type) is tuple:
            field_type, new_params = field_type
            field_params.update(new_params)

        # Add max_length for all str fields.
        if field_type == 'str' and row[3]:
            max_length = int(row[3])
            if max_length != -1:
                field_params['max_len'] = max_length

        if field_type == 'Decimal':
            if row[4] is None or row[5] is None:
                field_notes.append(
                    'scale and precision have been guessed, as this '
                    'database handles decimal fields as float')
                field_params['precision'] = row[4] if row[4] is not None else 10
                field_params['scale'] = row[5] if row[5] is not None else 5
            else:
                field_params['precision'] = row[4]
                field_params['scale'] = row[5]

        return field_type, field_params, field_notes
