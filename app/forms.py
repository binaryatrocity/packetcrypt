from flask.ext.wtf import Form
from wtforms import TextField, SubmitField, TextAreaField
from wtforms.validators import Required

class TicketForm(Form):
    subject = TextField('Subject', validators = [Required()])
    body = TextAreaField('Message', validators = [Required()])

