import re
import warnings

field_size_re = re.compile(r'^\s*(?:var)?char\s*\(\s*(\d+)\s*\)\s*$')


from .base import (
    Introspection as BaseIntrospection,
    FieldInfo, TableInfo, NamedList
)

def get_field_size(name):
    """ Extract the size number from a "varchar(11)" type name """
    m = field_size_re.search(name)
    return int(m.group(1)) if m else None


class Introspection(BaseIntrospection):
    data_types_reverse = {
        'bool': 'bool',
        'boolean': 'bool',
        'smallint': 'int',
        'smallint unsigned': 'int',
        'smallinteger': 'int',
        'int': 'int',
        'integer': 'int',
        'bigint': 'int',
        'integer unsigned': 'int',
        'decimal': 'Decimal',
        'real': 'float',
        'text': 'LongStr',
        'char': 'str',
        'blob': 'buffer',
        'date': 'date',
        'datetime': 'datetime',
        'time': 'time',
    }

    imports = {
        'LongStr': 'from pony.orm.ormtypes import LongStr',
        'datetime': 'from datetime import datetime',
        'time': 'from datetime import time',
        'date': 'from datetime import date',
        'Decimal': 'from decimal import Decimal',
        'buffer': 'from pony.py23compat import buffer',
    }

    def get_field_type(self, data_type, description):
        opts = None
        data_type = data_type.lower()
        try:
            field_type = self.data_types_reverse[data_type]
        except KeyError:
            field_type = 'str'
            size = get_field_size(data_type)
            assert size is not None
            opts = {'max_len': size}
        _import = self.imports.get(field_type)
        if description.default and 'nextval' in description.default:
            # ???
            if field_type == 'int':
                return 'AUTO', opts, _import
        return field_type, opts, _import

    def get_table_list(self, cursor):
        """Return a list of table and view names in the current database."""
        # Skip the sqlite_sequence system table used for autoincrement key
        # generation.
        cursor.execute("""
            SELECT name, type FROM sqlite_master
            WHERE type in ('table', 'view') AND NOT name='sqlite_sequence'
            ORDER BY name""")
        return [TableInfo(row[0], row[1][0]) for row in cursor.fetchall()]

    def get_table_description(self, cursor, table_name):
        """
        Return a description of the table with the DB-API cursor.description
        interface.
        """
        return [
            FieldInfo(
                info['name'],
                info['type'],
                None,
                info['size'],
                None,
                None,
                info['null_ok'],
                info['default'],
            ) for info in self._table_info(cursor, table_name)
        ]

    def get_relations(self, cursor, table_name):
        """
        Return a dictionary of {field_name: (field_name_other_table, other_table)}
        representing all relationships to the given table.
        """
        # Dictionary of relations to return
        relations = {}

        # Schema for this table
        cursor.execute("SELECT sql FROM sqlite_master WHERE tbl_name = ? AND type = ?", [table_name, "table"])
        try:
            results = cursor.fetchone()[0].strip()
        except TypeError:
            # It might be a view, then no results will be returned
            return relations
        results = results[results.index('(') + 1:results.rindex(')')]

        # Walk through and look for references to other tables. SQLite doesn't
        # really have enforced references, but since it echoes out the SQL used
        # to create the table we can look for REFERENCES statements used there.
        for field_desc in results.split(','):
            field_desc = field_desc.strip()
            if field_desc.startswith("UNIQUE"):
                continue

            m = re.search(r'references (\S*) ?\(["|]?(.*)["|]?\)', field_desc, re.I)
            if not m:
                continue
            table, column = [s.strip('"') for s in m.groups()]

            if field_desc.startswith("FOREIGN KEY"):
                # Find name of the target FK field
                m = re.match(r'FOREIGN KEY\s*\(([^\)]*)\).*', field_desc, re.I)
                field_name = m.groups()[0].strip('"')
            else:
                field_name = field_desc.split()[0].strip('"')

            cursor.execute("SELECT sql FROM sqlite_master WHERE tbl_name = ?", [table])
            result = cursor.fetchall()[0]
            other_table_results = result[0].strip()
            li, ri = other_table_results.index('('), other_table_results.rindex(')')
            other_table_results = other_table_results[li + 1:ri]

            for other_desc in other_table_results.split(','):
                other_desc = other_desc.strip()
                if other_desc.startswith('UNIQUE'):
                    continue

                other_name = other_desc.split(' ', 1)[0].strip('"')
                if other_name == column:
                    relations[field_name] = (other_name, table)
                    break

        return relations

    def get_key_columns(self, cursor, table_name):
        """
        Return a list of (column_name, referenced_table_name, referenced_column_name)
        for all key columns in given table.
        """
        key_columns = []

        # Schema for this table
        cursor.execute("SELECT sql FROM sqlite_master WHERE tbl_name = ? AND type = ?", [table_name, "table"])
        results = cursor.fetchone()[0].strip()
        results = results[results.index('(') + 1:results.rindex(')')]

        # Walk through and look for references to other tables. SQLite doesn't
        # really have enforced references, but since it echoes out the SQL used
        # to create the table we can look for REFERENCES statements used there.
        for field_index, field_desc in enumerate(results.split(',')):
            field_desc = field_desc.strip()
            if field_desc.startswith("UNIQUE"):
                continue

            m = re.search(r'"(.*)".*references (.*) \(["|](.*)["|]\)', field_desc, re.I)
            if not m:
                continue

            # This will append (column_name, referenced_table_name, referenced_column_name) to key_columns
            key_columns.append(tuple(s.strip('"') for s in m.groups()))

        return key_columns

    # def get_indexes(self, cursor, table_name):
    #     warnings.warn(
    #         "get_indexes() is deprecated in favor of get_constraints().",
    #         RemovedInDjango21Warning, stacklevel=2
    #     )
    #     indexes = {}
    #     for info in self._table_info(cursor, table_name):
    #         if info['pk'] != 0:
    #             indexes[info['name']] = {'primary_key': True,
    #                                      'unique': False}
    #     cursor.execute('PRAGMA index_list(%s)' % self.connection.ops.quote_name(table_name))
    #     # seq, name, unique
    #     for index, unique in [(field[1], field[2]) for field in cursor.fetchall()]:
    #         cursor.execute('PRAGMA index_info(%s)' % self.connection.ops.quote_name(index))
    #         info = cursor.fetchall()
    #         # Skip indexes across multiple fields
    #         if len(info) != 1:
    #             continue
    #         name = info[0][2]  # seqno, cid, name
    #         indexes[name] = {'primary_key': indexes.get(name, {}).get("primary_key", False),
    #                          'unique': unique}
    #     return indexes

    def get_primary_key_column(self, cursor, table_name):
        """Return the column name of the primary key for the given table."""
        # Don't use PRAGMA because that causes issues with some transactions
        cursor.execute("SELECT sql FROM sqlite_master WHERE tbl_name = ? AND type = ?", [table_name, "table"])
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Table %s does not exist" % table_name)
        results = row[0].strip()
        results = results[results.index('(') + 1:results.rindex(')')]
        for field_desc in results.split(','):
            field_desc = field_desc.strip()
            m = re.search('"(.*)".*PRIMARY KEY( AUTOINCREMENT)?', field_desc)
            if m:
                return m.groups()[0]
        return None

    def _table_info(self, cursor, name):
        quote_name = self.provider.quote_name
        cursor.execute('PRAGMA table_info(%s)' % quote_name(name))
        # cid, name, type, notnull, default_value, pk
        return [{
            'name': field[1],
            'type': field[2],
            'size': get_field_size(field[2]),
            'null_ok': not field[3],
            'default': field[4],
            'pk': field[5],  # undocumented
        } for field in cursor.fetchall()]

    def get_constraints(self, cursor, table_name):
        """
        Retrieve any constraints or keys (unique, pk, fk, check, index) across
        one or more columns.
        """
        constraints = {}
        # Get the index info
        quote_name = self.provider.quote_name
        cursor.execute("PRAGMA index_list(%s)" % quote_name(table_name))
        for row in cursor.fetchall():
            # Sqlite3 3.8.9+ has 5 columns, however older versions only give 3
            # columns. Discard last 2 columns if there.
            number, index, unique = row[:3]
            # Get the index info for that index
            cursor.execute('PRAGMA index_info(%s)' % quote_name(index))
            for index_rank, column_rank, column in cursor.fetchall():
                if index not in constraints:
                    constraints[index] = {
                        "columns": [],
                        "primary_key": False,
                        "unique": bool(unique),
                        "foreign_key": False,
                        "check": False,
                        "index": True,
                    }
                constraints[index]['columns'].append(column)
            # Add type and column orders for indexes
            if constraints[index]['index'] and not constraints[index]['unique']:
                # SQLite doesn't support any index type other than b-tree
                # constraints[index]['type'] = Index.suffix
                cursor.execute(
                    "SELECT sql FROM sqlite_master "
                    "WHERE type='index' AND name=%s" % quote_name(index)
                )
                orders = []
                # There would be only 1 row to loop over
                for sql, in cursor.fetchall():
                    order_info = sql.split('(')[-1].split(')')[0].split(',')
                    orders = ['DESC' if info.endswith('DESC') else 'ASC' for info in order_info]
                constraints[index]['orders'] = orders
        # Get the PK
        pk_column = self.get_primary_key_column(cursor, table_name)
        if pk_column:
            # SQLite doesn't actually give a name to the PK constraint,
            # so we invent one. This is fine, as the SQLite backend never
            # deletes PK constraints by name, as you can't delete constraints
            # in SQLite; we remake the table with a new PK instead.
            constraints["__primary__"] = {
                "columns": [pk_column],
                "primary_key": True,
                "unique": False,  # It's not actually a unique constraint.
                "foreign_key": False,
                "check": False,
                "index": False,
            }
        return constraints
