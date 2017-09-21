
from pony.orm import *

db = Database()

class A(db.Entity):
    col = Required(str)
    b = Optional('B')

class B(db.Entity):
    a = Required('A')



# sql_debug(1)
db.bind(**{
    'provider': 'sqlite',
    'filename': 'db1.sqlite',
    'create_db': 1,
})
db.generate_mapping(create_tables=1)