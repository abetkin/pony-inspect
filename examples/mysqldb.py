
from pony.orm import *

db = Database()

class A(db.Entity):
    col = Required(str)
    b = Optional('B')

class B(db.Entity):
    a = Required('A')



sql_debug(1)
db.bind(**{
    'provider': 'mysql',
    'host': 'localhost',
    'database': 'db1',
    'user': 'root',
    'password': 'r23t',
})
db.generate_mapping(create_tables=1)