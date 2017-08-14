# This is an auto-generated module with pony entities.
# Feel free to rename the models, but don't rename _table_ or field names.

from pony.orm import *

db = Database()


class Email(db.Entity):
    _table_ = "email"
    email = Required(str)
    is_personal = Required(bool)
    employee = Required("Employee")


class Employee(db.Entity):
    _table_ = "employee"
    first_name = Required(str)
    last_name = Required(str)
    email_set = Set("Email")
    location = Required("Location")
    manager = Required("Employee", reverse="employee_set")
    employee_set = Set("Employee", reverse="manager")
    group_set = Set("Group")
    position_set = Set("Position")
    im_username_set = Set("ImUsername")
    phone_set = Set("Phone")


class Location(db.Entity):
    _table_ = "location"
    name = Required(str)
    address = Required(str)
    employee_set = Set("Employee")


class Group(db.Entity):
    _table_ = "group"
    name = Required(str)
    employee_set = Set("Employee")


class Position(db.Entity):
    _table_ = "position"
    title = PrimaryKey(str)
    employee_set = Set("Employee")


class ImUsername(db.Entity):
    _table_ = "im_username"
    username = Required(str)
    employee = Required("Employee")
    messenger_type = Required("Instantmessenger")
    PrimaryKey(employee, messenger_type)


class Instantmessenger(db.Entity):
    _table_ = "instantmessenger"
    name = PrimaryKey(str)
    im_username_set = Set("ImUsername")


class Phone(db.Entity):
    _table_ = "phone"
    number = Required(str)
    is_personal = Required(bool)
    employee = Required("Employee")
    type = Required("Phonetype")


class Phonetype(db.Entity):
    _table_ = "phonetype"
    name = PrimaryKey(str)
    phone_set = Set("Phone")

sql_debug(1)
db.bind(**{
    'provider': 'postgres',
    'host': 'localhost',
    'database': 'cd',
    'user': 'postgres',
    'password': 'postgres',
})
db.generate_mapping(create_tables=1)