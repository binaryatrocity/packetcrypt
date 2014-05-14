from app import db
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.security import UserMixin, RoleMixin

roles_users = db.Table('roles_users',
        db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
        db.Column('role_id', db.Integer(), db.ForeignKey('role.id')))

class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    active = db.Column(db.Boolean())
    confirmed_at = db.Column(db.DateTime())
    roles = db.relationship('Role', secondary=roles_users, backref=db.backref('users', lazy='dynamic'))
    tickets = db.relationship('Ticket', backref='creator', lazy='dynamic')
    invoices = db.relationship('Invoice', backref='customer', lazy='dynamic')

    def __repr__(self):
        return '<User %r>' % (self.email)

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(140), unique=True)
    body = db.Column(db.String(2000))
    created = db.Column(db.DateTime)
    timestamp = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __repr__(self):
        return '<Ticket %r>' % (self.subject)

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    is_confirmed = db.Column(db.Boolean())
    paid = db.Column(db.Boolean())
    datepaid = db.Column(db.DateTime)
    datecreated = db.Column(db.DateTime)
    dateends = db.Column(db.DateTime)
    total_btc = db.Column(db.Float)
    exchange_rate_when_paid = db.Column(db.Float)
    address = db.Column(db.String(34))
    confirmations = db.Column(db.Integer)
    transaction_hash = db.Column(db.String)
    input_transaction_hash = db.Column(db.String)
    value_paid = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __repr__(self):
        return '<Invoice %r>' % (self.id)
