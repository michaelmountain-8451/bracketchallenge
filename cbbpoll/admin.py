from flask import redirect, url_for
from flask_admin import Admin
from flask_admin.actions import action
from flask_admin.base import AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.form.fields import Select2Field
from flask_login import current_user
from wtforms.validators import InputRequired
from flask_wtf import FlaskForm as flask_wtf__Form
from datetime import datetime, timedelta
from botactions import update_flair

from cbbpoll import app, db
from models import User, Team, Game


def teamChoices():
    try:
        teams = Team.query.all()
        choices = [('-1', '')]
        for team in teams:
            choice = ((team.id, str(team)))
            choices.append(choice)
    except Exception:
        choices = None
    return choices


class AdminModelView(ModelView):
    form_base_class = flask_wtf__Form
    def is_accessible(self):
        return current_user.is_admin()


class MyAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        if not current_user.is_admin():
            return redirect(url_for('index'))
        return super(MyAdminIndexView, self).index()


class UserAdmin(AdminModelView):
    column_display_pk = True
    form_columns = ['nickname', 'email', 'emailConfirmed', 'role', 'flair_team', 'flair', 'emailReminders', 'pmReminders']
    column_list = ['id', 'nickname', 'email', 'emailConfirmed', 'role', 'is_voter', 'applicationFlag', 'flair_team.full_name' ]
    column_sortable_list = ('id', 'nickname', 'email', 'emailConfirmed', 'role', 'applicationFlag', 'flair_team.full_name')
    column_searchable_list = ('nickname', 'email')
    form_overrides = dict(role=Select2Field)
    column_filters = ('flair_team.full_name', 'flair_team.conference')
    form_args = dict(
    # Pass the choices to the `SelectField`
        role=dict(
        choices=[('u', 'user'), ('a', 'admin')]
        ))

    @action('promote', 'Make Voter', 'Are you sure you want to grant voter status to the selected users?')
    def action_promote(self, ids):
        pass

    @action('demote', 'Revoke Voter Status', 'Are you sure you want to revoke voter status from the selected users?')
    def action_demote(self, ids):
        pass

    @action('update_flair', 'Update Flair', 'Update flair on the selected users? This may take some time and increase response time')
    def action_update_flair(self, ids):
        pass

    @action('voter_flag','Flag for Voting', 'Flag selected users for voting?')
    def action_voter_flag(self, ids):
        pass

    @action('voter_unflag','Unflag for Voting', 'Unflag selected users for voting?')
    def action_voter_unflag(self, ids):
        pass


class TeamAdmin(AdminModelView):
    column_display_pk = True
    page_size = 100
    form_columns = ['full_name', 'short_name', 'nickname', 'conference', 'flair', 'png_name']
    column_list = ['id', 'full_name', 'short_name', 'nickname', 'conference', 'flair', 'png_name']
    column_searchable_list = ('full_name', 'short_name', 'nickname', 'conference')


class GameAdmin(AdminModelView):
    column_display_pk = True
    page_size = 100
    form_columns = ['conference_id', 'point_value', 'home_team_id', 'away_team_id', 'next_game_id', 'winner_is_home',
                    'is_championship']
    column_list = ['id', 'conference_id', 'point_value', 'home_team_id', 'away_team_id', 'next_game_id',
                   'winner_is_home', 'is_championship', 'result', 'home_team', 'away_team']
    column_searchable_list = ('conference_id', 'point_value', 'home_team_id', 'away_team_id', 'next_game_id',
                              'winner_is_home', 'is_championship')


# Create admin
admin = Admin(name='User Poll Control Panel', index_view=MyAdminIndexView(endpoint="admin"))
admin.init_app(app)
admin.add_view(TeamAdmin(Team, db.session))
admin.add_view(UserAdmin(User, db.session))
admin.add_view(GameAdmin(Game, db.session))
