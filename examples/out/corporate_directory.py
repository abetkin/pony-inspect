# This is an auto-generated module with pony entities.
# Feel free to rename the models, but don't rename _table_ or field names.

from pony.orm import *

db = Database()


class Email(db.Entity):
    _table_ = "email"
    email = Required(str)
    is_personal = Required(bool)
    employee = Required("Employee", reverse='email_set')


class Employee(db.Entity):
    _table_ = "employee"
    first_name = Required(str)
    last_name = Required(str)
    manager = Optional("Employee", reverse='employee_set')
    location = Required("Location", reverse='employee_set')
    email_set = Set("Email", reverse="employee")
    employee_set = Set("Employee", reverse="manager")
    employeegroups_set = Set("EmployeeGroups", reverse="employee")
    employeepositions_set = Set("EmployeePositions", reverse="employee")
    imusername_set = Set("ImUsername", reverse="employee")
    phone_set = Set("Phone", reverse="employee")


class EmployeeGroups(db.Entity):
    _table_ = "employee_groups"
    employee = Required("Employee", reverse='employeegroups_set')
    group = Required("Group", reverse='employeegroups_set')
    PrimaryKey(employee, group)


class EmployeePositions(db.Entity):
    _table_ = "employee_positions"
    employee = Required("Employee", reverse='employeepositions_set')
    position = Required("Position", reverse='employeepositions_set')
    PrimaryKey(employee, position)


class Group(db.Entity):
    _table_ = "group"
    name = Required(str)
    employeegroups_set = Set("EmployeeGroups", reverse="group")


class ImUsername(db.Entity):
    _table_ = "im_username"
    employee = Required("Employee", reverse='imusername_set')
    messenger_type = Required("Instantmessenger", reverse='imusername_set')
    username = Required(str)
    PrimaryKey(employee, messenger_type)


class Instantmessenger(db.Entity):
    _table_ = "instantmessenger"
    name = PrimaryKey(str)
    imusername_set = Set("ImUsername", reverse="messenger_type")


class Location(db.Entity):
    _table_ = "location"
    name = Required(str)
    address = Required(str)
    employee_set = Set("Employee", reverse="location")


class Phone(db.Entity):
    _table_ = "phone"
    number = Required(str)
    is_personal = Required(bool)
    employee = Required("Employee", reverse='phone_set')
    type = Required("Phonetype", reverse='phone_set')


class Phonetype(db.Entity):
    _table_ = "phonetype"
    name = PrimaryKey(str)
    phone_set = Set("Phone", reverse="type")


class Position(db.Entity):
    _table_ = "position"
    title = PrimaryKey(str)
    employeepositions_set = Set("EmployeePositions", reverse="position")

db.bind(**{
    'provider': 'postgres',
    'host': 'localhost',
    'database': 'example_simple',
    'user': 'postgres',
    'password': 'postgres',
})
db.generate_mapping(create_tables=1)