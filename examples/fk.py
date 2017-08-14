from pony.orm import *

db = Database()

class A(db.Entity):
    bs = Set('B')

class B(db.Entity):
    a = Required('A')

db.bind(**{
    'provider': 'postgres',
    'host': 'localhost',
    'database': '_fk',
    'user': 'postgres',
    'password': 'postgres',
})
db.generate_mapping(create_tables=1)