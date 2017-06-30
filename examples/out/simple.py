# This is an auto-generated module with pony entities.
# Feel free to rename the models, but don't rename _table_ or field names.

from pony.orm import *

db = Database()


class A(db.Entity):
    _table_ = "a"
    ab_set = Set("AB", reverse="a")


class AB(db.Entity):
    _table_ = "a_b"
    a = Required("A", reverse='ab_set')
    b = Required("B", reverse='ab_set')
    PrimaryKey(a, b)


class B(db.Entity):
    _table_ = "b"
    ab_set = Set("AB", reverse="b")

sql_debug(1)
db.bind(**{
    'provider': 'postgres',
    'host': 'localhost',
    'database': 'example_simple',
    'user': 'postgres',
    'password': 'postgres',
})
db.generate_mapping(create_tables=1)