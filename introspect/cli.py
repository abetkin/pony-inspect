'''
Usage:
    introspect --database=DATABASE

Options:
    DATABASE  path to pony.orm.Database
'''

from pony.utils import cached_property

import keyword
import re
from collections import OrderedDict

from .utils import import_obj

from docopt import docopt

from pony.orm import Database

import os
from textwrap import dedent

from .postgres import Introspection

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
    
    @cached_property
    def reverse_relations(self):
        return {}

    @cached_property
    def relations_data(self):
        return {}
    
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

    def _get_output(self):
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

        table2model = self.table2model

        def strip_prefix(s):
            return s[1:] if s.startswith("u'") else s

        with connection.cursor() as cursor:
            yield 'db = Database()'
            known_models = []
            tables_to_introspect = introspection.table_names(cursor)


            for table_name in tables_to_introspect:
                try:
                    relations = self.relations_data[table_name] = introspection.get_relations(cursor, table_name)
                except NotImplementedError:
                    if os.environ.get('DEBUG'):
                        raise
                    relations = self.relations_data[table_name] = {}
                # populate reverse relations
                model_name = self.table2model(table_name)
                rattr = model_name.lower()
                for column_name, (_attr, ref_table) in relations.items():
                    att_name, *_ = self.normalize_col_name(column_name, (), True)
                    ref = self.reverse_relations.setdefault(ref_table, {})
                    keys = list(filter(lambda key: key.startswith(rattr), ref))
                    postfix = f'_{len(keys)}' if keys else ''
                    key = f"{rattr}_set{postfix}"
                    ref[key] = {
                        'attr': att_name,
                        'model': model_name,
                    }

            for table_name in tables_to_introspect:
                if self.is_pony_table(table_name):
                    continue
                try:
                    relations = self.relations_data[table_name]
                    try:
                        constraints = introspection.get_constraints(cursor, table_name)
                    except NotImplementedError:
                        if os.environ.get('DEBUG'):
                            raise
                        constraints = {}
                    primary_key_column = introspection.get_primary_key_column(cursor, table_name)
                    unique_columns = [
                        c['columns'][0] for c in constraints.values()
                        if c['unique'] and len(c['columns']) == 1
                    ]
                    table_description = introspection.get_table_description(cursor, table_name)
                except Exception as e:
                    if os.environ.get('DEBUG'):
                        raise
                    yield f"# Unable to inspect table '{table_name}'"
                    yield f"# The error was: {e}"
                    continue

                yield ''
                yield ''
                model_name = table2model(table_name)
                yield f'class {model_name}(db.Entity):'
                yield f'    _table_ = "{table_name}"'
                known_models.append(model_name)
                used_column_names = []  # Holds column names used in the table so far
                column_to_field_name = {}  # Maps column names to names of model fields

                for row in table_description:
                    comment_notes = []  # Holds Field notes, to be displayed in a Python comment.
                    extra_params = OrderedDict()  # Holds Field parameters such as 'db_column'.
                    column_name = row[0]
                    is_relation = column_name in relations

                    att_name, params, notes = self.normalize_col_name(
                        column_name, used_column_names, is_relation)
                    extra_params.update(params)
                    comment_notes.extend(notes)

                    used_column_names.append(att_name)
                    column_to_field_name[column_name] = att_name
                    field_kwargs = {}

                    # Add primary_key and unique, if necessary.
                    if column_name == primary_key_column:
                        extra_params['primary_key'] = True
                    elif column_name in unique_columns:
                        field_kwargs['unique'] = True

                    if is_relation:
                        ref_table = relations[column_name][1]
                        rel_to = table2model(ref_table)
                        field_type = f'"{rel_to}"'
                        for rattr, d in self.reverse_relations[ref_table].items():
                            if d['attr'] == att_name and d['model'] == model_name:
                                break
                        else:
                            assert 0
                        field_kwargs['reverse'] = rattr
                    else:
                        # Calling `get_field_type` to get the field type string and any
                        # additional parameters and notes.
                        field_type, field_params, field_notes = self.get_field_type(connection, table_name, row)
                        extra_params.update(field_params)
                        field_kwargs.update(field_params)
                        comment_notes.extend(field_notes)


                    # Don't output 'id = meta.AutoField(primary_key=True)', because
                    # that's assumed if it doesn't exist.
                    if att_name == 'id' and extra_params == {'primary_key': True}:
                        if field_type == 'AUTO':
                            continue

                    # Add 'null' and 'blank', if the 'null_ok' flag was present in the
                    # table description.
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

                    if extra_params.get('null'):
                        field_desc = f'{att_name} = Optional({field_type}{kwargs_list})'
                    else:
                        field_desc = f'{att_name} = Required({field_type}{kwargs_list})'

                    if comment_notes:
                        field_desc += f'  # {join(comment_notes)}'
                    yield f'    {field_desc}' 
                
                # TODO unique together


                ref = self.reverse_relations.get(table_name)
                if not ref:
                    continue
                for rattr, d in ref.items():
                    yield f'''    {rattr} = Set("{d['model']}", reverse="{d['attr']}")'''

                # for meta_line in self.get_meta(table_name, constraints, column_to_field_name):
                #     yield meta_line


    def normalize_col_name(self, col_name, used_column_names, is_relation):
        """
        Modify the column name to make it Python-compatible as a field name
        """
        field_params = {}
        field_notes = []

        new_name = col_name.lower()
        if new_name != col_name:
            field_notes.append('Field name made lowercase.')

        # if is_relation:
        #     if new_name.endswith('_id'):
        #         new_name = new_name[:-3]
        #     else:
        #         field_params['db_column'] = col_name

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

        if new_name in used_column_names:
            num = 0
            while '%s_%d' % (new_name, num) in used_column_names:
                num += 1
            new_name = '%s_%d' % (new_name, num)
            field_notes.append('Field renamed because of name conflict.')

        if col_name != new_name:
            field_params['db_column'] = col_name

        return new_name, field_params, field_notes

    def get_field_type(self, connection, table_name, row):
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

    # def get_meta(self, table_name, constraints, column_to_field_name):
    #     """
    #     Return a sequence comprising the lines of code necessary
    #     to construct the inner Meta class for the model corresponding
    #     to the given database table name.
    #     """
    #     unique_together = []
    #     for index, params in constraints.items():
    #         if params['unique']:
    #             columns = params['columns']
    #             if len(columns) > 1:
    #                 # we do not want to include the u"" or u'' prefix
    #                 # so we build the string rather than interpolate the tuple
    #                 tup = '(' + ', '.join("'%s'" % column_to_field_name[c] for c in columns) + ')'
    #                 unique_together.append(tup)
    #     meta = ["",
    #             "    class Meta:",
    #             "        managed = False",
    #             "        db_table = '%s'" % table_name]
    #     if unique_together:
    #         tup = '(' + ', '.join(unique_together) + ',)'
    #         meta += ["        unique_together = %s" % tup]
    #     return meta

        
