from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask.ext.security import SQLAlchemyUserDatastore, Security, user_registered
from flask.ext.admin import Admin
from flask.ext.admin.contrib.sqla import ModelView
from config import ADMINS, MAILCONF, SECURITY_EMAIL_SENDER

app = Flask(__name__)
app.config.from_object('config')

# Setup SQL database and ORM 
db = SQLAlchemy(app)

# Initialize Flask-Security
from models import User, Role, Ticket, Invoice
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)
mail = Mail(app)

# Initialize Flask-Admin
from app import admin
admin = Admin(app, name='PacketCrypt', index_view=admin.AdminIndex())
admin.add_view(ModelView(User, db.session))
admin.add_view(ModelView(Ticket, db.session))
admin.add_view(ModelView(Invoice, db.session))

@app.before_first_request
def initialize():
    try:
        db.create_all()
        user = user_datastore.find_user(email='br4n@atr0phy.net')
        if not user:
            user = user_datastore.create_user(email='br4n@atr0phy.net', password='packetcrypt')
            user_datastore.add_role_to_user(user, 'Admin')
            app.logger.info("First run, create default admin user")
            for role in ('Admin', 'User'):
                user_datastore.create_role(name=role)
        db.session.commit()
    except Exception, e:
        app.logger.error(str(e))

@user_registered.connect_via(app)
def on_user_registered(sender, **extra):
    default_role = user_datastore.find_role("User")
    user_datastore.add_role_to_user(user, default_role)
    db.session.commit()

# Import views
from app import views

if not app.debug:
    import logging
    from logging.handlers import SMTPHandler, RotatingFileHandler
    credentials = None
    if MAILCONF['MAIL_USERNAME'] or MAILCONF['MAIL_PASSWORD']:
        credentials = (MAILCONF['MAIL_USERNAME'], MAILCONF['MAIL_PASSWORD'])
    mail_handler = SMTPHandler((MAILCONF['MAIL_SERVER'], MAILCONF['MAIL_PORT']), SECURITY_EMAIL_SENDER, ADMINS, 'PacketCrypt failure', credentials)
    mail_handler.setLevel(logging.ERROR)
    app.logger.addHandler(mail_handler)
    file_handler = RotatingFileHandler('app.log', 'a', 1 * 1024 * 1024, 10)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    app.logger.setLevel(logging.INFO)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.info('PacketCrypt startup')
