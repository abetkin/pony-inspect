from pony.orm import *

db = Database()

class A(db.Entity):
    b = Set('B')

class B(db.Entity):
    a = Set('A')

db.bind(**{
    'provider': 'postgres',
    'host': 'localhost',
    'database': 'example_simple',
    'user': 'postgres',
    'password': 'postgres',
})
db.generate_mapping(create_tables=1)