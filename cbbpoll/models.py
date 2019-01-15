from flask import url_for
from datetime import datetime, timedelta
from cbbpoll import db, app
from cbbpoll.message import send_reddit_pm
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from sqlalchemy import select, desc, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from flask_sqlalchemy import models_committed
from flask_login import AnonymousUserMixin


def on_models_committed(_, changes):
    for obj, change in changes:
        if change == 'insert' and hasattr(obj, '__commit_insert__'):
            obj.__commit_insert__()

models_committed.connect(on_models_committed, sender=app)


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer,
                   primary_key=True,
                   autoincrement=True)

    nickname = db.Column(db.String(20), index=True)
    email = db.Column(db.String(120), index=True)
    emailConfirmed = db.Column(db.Boolean, default=False)
    role = db.Column(db.Enum('u', 'a'), default='u')
    accessToken = db.Column(db.String(30))
    refreshToken = db.Column(db.String(30))
    refreshAfter = db.Column(db.DateTime)
    emailReminders = db.Column(db.Boolean, default=False)
    pmReminders = db.Column(db.Boolean, default=False)
    applicationFlag = db.Column(db.Boolean, default=False)
    ballots = []

    voterEvents = []

    voterApplication = {}

    @property
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def is_admin(self):
        return self.role == 'a'

    @property
    def team(self):
        return None

    @property
    def conference(self):
        if self.team:
            return self.team.conference
        return None

    @hybrid_property
    def remind_viaEmail(self):
        return self.emailConfirmed & self.emailReminders

    def get_id(self):
        return unicode(self.id)

    def generate_confirmation_token(self, expiration=3600, email=email):
        s = Serializer(app.config['SECRET_KEY'], expiration)
        return s.dumps({'confirm': self.id, 'email': email})

    def confirm(self, token):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('confirm') != self.id:
            return False
        if data.get('email') == self.email and self.emailConfirmed:
            # Avoid a database write, but don't want to give an error to user.
            return True
        self.email = data.get('email')
        self.emailConfirmed = True
        db.session.add(self)
        db.session.commit()
        return True


    @hybrid_property
    def remind_viaRedditPM(self):
        return False

    @hybrid_property
    def is_voter(self):
        return False

    @is_voter.expression
    def is_voter(cls):
        return False

    @is_voter.setter
    def is_voter(self, value):
        pass

    @hybrid_method
    def was_voter_at(self, timestamp):
        return False

    @was_voter_at.expression
    def was_voter_at(cls, timestamp):
        return False

    def name_with_flair(self, size=30):
        return str(self.nickname)

    def __repr__(self):
        return '<User %r>' % self.nickname

    def __str__(self):
        return str(self.nickname)


class AnonymousUser(AnonymousUserMixin):
    def is_admin(self):
        return False


class Team(db.Model):
    __tablename__ = 'team'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(75))
    short_name = db.Column(db.String(50))
    nickname = db.Column(db.String(50))
    png_name = db.Column(db.String(50))
    conference = db.Column(db.String(50))

    def png_url(self, size=30):
        return "http://cdn-png.si.com//sites/default/files/teams/basketball/cbk/logos/%s_%s.png" % (self.png_name, size)

    def logo_html(self, size=30):
        if size == 30 or size == 23:
            return "<span class=logo%s><img src='%s' class='logo%s-%s' alt=\"%s Logo\"></span>" % \
                   (size, url_for('static', filename='img/logos_%s.png' % size), size, self.png_name, self.full_name)
        else:
            return "<img src='%s' alt='%s Logo'>" % (self.png_url(size), self.full_name)

    def __repr__(self):
        if self.short_name:
            return '<Team %r>' % self.short_name
        else:
            return '<Team %r>' % self.full_name

    def __str__(self):
        if self.short_name:
            return'%s (%s)' % (self.short_name, self.full_name)
        else:
            return self.full_name




class Conference(db.Model):
    __tablename__  = 'conference'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160))
    year = db.Column(db.Integer)
    games = db.relationship('Game', backref='conference')


class Game(db.Model):
    __tablename__ = 'game'
    id = db.Column(db.Integer, primary_key=True)
    conference_id = db.Column(db.Integer, db.ForeignKey('conference.id'))
    point_value = db.Column(db.Float)
    home_team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    away_team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    next_game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=True)
    winner_is_home = db.Column(db.Boolean, nullable=True)
    is_championship = db.Column(db.Boolean)
    __table_args__ = (
        UniqueConstraint('next_game_id', 'winner_is_home', name='one_winner'),
        {})
    result = db.relationship('Result', uselist=False, back_populates='game')
    home_team = db.relationship('Team', foreign_keys=[home_team_id])
    away_team = db.relationship('Team', foreign_keys=[away_team_id])


class Result(db.Model):
    __tablename = 'result'
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'))
    winning_team_id = db.Column(db.Integer, db.ForeignKey('team.id'))
    game = db.relationship('Game', back_populates='result')


class Prediction(db.Model):
    __tablename__ = 'prediction'
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    winning_team_id = db.Column(db.Integer, db.ForeignKey('team.id'))
    game = db.relationship('Game', backref='predictions')


