from collections import namedtuple

# Structure returned by DatabaseIntrospection.get_table_list()
TableInfo = namedtuple('TableInfo', ['name', 'type'])

# Structure returned by the DB-API cursor.description interface (PEP 249)

# def FieldInfo(*args):
#     return _FieldInfo(args)

class NamedList(list):
    KEYS = ()

    def __getattr__(self, key):
        index = self.KEYS.index(key)
        return self[index]

    def __new__(cls, *args):
        ret = list.__new__(cls)
        ret.extend(args)
        return ret

    def __init__(self, *args):
        pass

class FieldInfo(NamedList):
    KEYS = 'name type_code display_size internal_size precision scale null_ok default'.split()


class Introspection:
    """Encapsulate backend-specific introspection utilities."""
    data_types_reverse = {}

    def __init__(self, connection, **kw):
        self.connection = connection
        self.__dict__.update(**kw)

    def get_field_type(self, data_type, description):
        """
        Hook for a database backend to use the cursor description to
        match a Django field type to a database column.

        For Oracle, the column data_type on its own is insufficient to
        distinguish between a FloatField and IntegerField, for example.
        """
        return self.data_types_reverse[data_type], None

    def table_name_converter(self, name):
        """
        Apply a conversion to the name for the purposes of comparison.

        The default table name converter is for case sensitive comparison.
        """
        return name

    def column_name_converter(self, name):
        """
        Apply a conversion to the column name for the purposes of comparison.

        Use table_name_converter() by default.
        """
        return self.table_name_converter(name)

    def table_names(self, cursor=None, include_views=False):
        """
        Return a list of names of all tables that exist in the database.
        Sort the returned table list by Python's default sorting. Do NOT use
        the database's ORDER BY here to avoid subtle differences in sorting
        order between databases.
        """
        def get_names(cursor):
            return sorted(ti.name for ti in self.get_table_list(cursor)
                          if include_views or ti.type == 't')
        if cursor is None:
            with self.connection.cursor() as cursor:
                return get_names(cursor)
        return get_names(cursor)

    # def get_table_list(self, cursor):
    #     """
    #     Return an unsorted list of TableInfo named tuples of all tables and
    #     views that exist in the database.
    #     """
    #     raise NotImplementedError('subclasses of BaseDatabaseIntrospection may require a get_table_list() method')

    # def django_table_names(self, only_existing=False, include_views=True):
    #     """
    #     Return a list of all table names that have associated Django models and
    #     are in INSTALLED_APPS.

    #     If only_existing is True, include only the tables in the database.
    #     """
    #     from django.apps import apps
    #     from django.db import router
    #     tables = set()
    #     for app_config in apps.get_app_configs():
    #         for model in router.get_migratable_models(app_config, self.connection.alias):
    #             if not model._meta.managed:
    #                 continue
    #             tables.add(model._meta.db_table)
    #             tables.update(
    #                 f.m2m_db_table() for f in model._meta.local_many_to_many
    #                 if f.remote_field.through._meta.managed
    #             )
    #     tables = list(tables)
    #     if only_existing:
    #         existing_tables = self.table_names(include_views=include_views)
    #         tables = [
    #             t
    #             for t in tables
    #             if self.table_name_converter(t) in existing_tables
    #         ]
    #     return tables

    # def installed_models(self, tables):
    #     """
    #     Return a set of all models represented by the provided list of table
    #     names.
    #     """
    #     from django.apps import apps
    #     from django.db import router
    #     all_models = []
    #     for app_config in apps.get_app_configs():
    #         all_models.extend(router.get_migratable_models(app_config, self.connection.alias))
    #     tables = list(map(self.table_name_converter, tables))
    #     return {
    #         m for m in all_models
    #         if self.table_name_converter(m._meta.db_table) in tables
    #     }

    # def sequence_list(self):
    #     """
    #     Return a list of information about all DB sequences for all models in
    #     all apps.
    #     """
    #     from django.apps import apps
    #     from django.db import models, router

    #     sequence_list = []

    #     for app_config in apps.get_app_configs():
    #         for model in router.get_migratable_models(app_config, self.connection.alias):
    #             if not model._meta.managed:
    #                 continue
    #             if model._meta.swapped:
    #                 continue
    #             for f in model._meta.local_fields:
    #                 if isinstance(f, models.AutoField):
    #                     sequence_list.append({'table': model._meta.db_table, 'column': f.column})
    #                     break  # Only one AutoField is allowed per model, so don't bother continuing.

    #             for f in model._meta.local_many_to_many:
    #                 # If this is an m2m using an intermediate table,
    #                 # we don't need to reset the sequence.
    #                 if f.remote_field.through is None:
    #                     sequence_list.append({'table': f.m2m_db_table(), 'column': None})

    #     return sequence_list

    # def get_key_columns(self, cursor, table_name):
    #     """
    #     Backends can override this to return a list of:
    #         (column_name, referenced_table_name, referenced_column_name)
    #     for all key columns in given table.
    #     """
    #     raise NotImplementedError('subclasses of BaseDatabaseIntrospection may require a get_key_columns() method')

    def get_primary_key_columns(self, cursor, table_name):
        """
        Return the name of the primary key column for the given table.
        """
        for constraint in self.get_constraints(cursor, table_name).values():
            if constraint['primary_key']:
                return constraint['columns']
        return None
