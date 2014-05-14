from flask.ext.security import current_user
from flask.ext.admin import AdminIndexView, BaseView, expose

class AdminIndex(AdminIndexView):
    def is_accessible(self):
        return current_user.has_role('Admin')


