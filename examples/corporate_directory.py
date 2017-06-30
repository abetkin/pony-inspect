from pony.orm import *


db = Database()


class Employee(db.Entity):
    first_name = Required(str)
    last_name = Required(str)
    manager = Optional('Employee', reverse='subordinates')
    subordinates = Set('Employee', reverse='manager')
    location = Required('Location')
    positions = Set('Position')
    groups = Set('Group')
    messengers = Set('IM_Username')
    phones = Set('Phone')
    emails = Set('Email')


class Location(db.Entity):
    name = Required(str)
    address = Required(str)
    employees = Set(Employee)


class Phone(db.Entity):
    number = Required(str)
    is_personal = Required(bool, default=False)
    employee = Required(Employee)
    type = Required('PhoneType')


class Email(db.Entity):
    email = Required(str)
    is_personal = Required(bool, default=False)
    employee = Required(Employee)


class Group(db.Entity):
    name = Required(str)
    employees = Set(Employee)


class Position(db.Entity):
    title = PrimaryKey(str)
    employees = Set(Employee)


class InstantMessenger(db.Entity):
    name = PrimaryKey(str)
    usernames = Set('IM_Username')


class IM_Username(db.Entity):
    employee = Required(Employee)
    messenger_type = Required(InstantMessenger)
    username = Required(str)
    PrimaryKey(employee, messenger_type)


class PhoneType(db.Entity):
    """Home, Mobile, Work"""
    name = PrimaryKey(str)
    phones = Set(Phone)


db.bind(**{
    'provider': 'postgres',
    'host': 'localhost',
    'database': 'codi',
    'user': 'postgres',
    'password': 'postgres',
})
db.generate_mapping(create_tables=1)