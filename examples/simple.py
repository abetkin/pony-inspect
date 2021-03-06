from pony.orm import *

db = Database()

class A(db.Entity):
    bs = Set('B')

class B(db.Entity):
    a_set = Set('A')

db.bind(**{
    'provider': 'postgres',
    'host': 'localhost',
    'database': 'simpl',
    'user': 'postgres',
    'password': 'postgres',
})
db.generate_mapping(create_tables=1)