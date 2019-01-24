from praw import Reddit
from flask import render_template, flash, redirect, session, url_for, request, g, abort, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from cbbpoll import app, db, lm, admin, message
from forms import EditProfileForm
from models import User, Team
from datetime import datetime
from pytz import utc, timezone
from botactions import update_flair
import re
from jinja2 import evalcontextfilter, Markup, escape
from sqlalchemy.exc import IntegrityError

eastern_tz = timezone('US/Eastern')

_paragraph_re = re.compile(r'(?:\r\n|\r|\n){2,}')


@app.template_filter()
@evalcontextfilter
def nl2br(eval_ctx, value):
    result = u'\n\n'.join(u'<p>%s</p>' % p.replace('\n', '<br>\n') for p in _paragraph_re.split(escape(value)))
    if eval_ctx.autoescape:
        result = Markup(result)
    return result


def user_by_nickname(name):
    return User.query.filter_by(nickname=name).first()

def timestamp(datetime):
    hour = datetime.hour % 12 or 12
    return '{dt:%A}, {dt:%B} {dt.day}, {dt:%Y} at {0}:{dt:%M}{dt:%p} {dt:%Z}'.format(hour, dt=datetime)


@app.before_request
def before_request():
    g.user = current_user


@lm.user_loader
def load_user(id):
    return User.query.get(int(id))


@app.errorhandler(403)
def forbidden_error(error):
    return render_template('403.html'), 403


@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500


@app.route('/')
def index():
    user = g.user

    return render_template('index.html',
                           title='Home',
                           user=user,
                           users=User.query,
                           teams=Team.query,)


@app.route('/authorize_callback', methods=['GET', 'POST'])
def authorized():
    reddit_state = request.args.get('state', '')
    reddit_code = request.args.get('code', '')
    if not reddit_state or not reddit_code:
        return redirect(url_for('index'))

    r = Reddit(
        client_id=app.config['REDDIT_CLIENT_ID'],
        client_secret=app.config['REDDIT_CLIENT_SECRET'],
        redirect_uri=app.config['REDDIT_REDIRECT_URI'],
        user_agent=app.config['REDDIT_USER_AGENT'],
    )

    refresh_token = r.auth.authorize(reddit_code)

    reddit_user = r.user.me()
    next_path = session['last_path']
    if reddit_state != session['oauth_state']:
        flash("Invalid state given, please try again.", 'danger')
        return redirect(next_path or url_for('index'))
    user = user_by_nickname(reddit_user.name)
    if user is None:
        nickname = reddit_user.name
        user = User(nickname=nickname,
                    role='u',
                    refreshToken=refresh_token)
    else:
        user.refreshToken = refresh_token
    db.session.add(user)
    db.session.commit()
    remember_me = False
    if 'remember_me' in session:
        remember_me = session['remember_me']
        session.pop('remember_me', None)
    login_user(user, remember=remember_me)
    update_flair(user, r.user.me())
    return redirect(next_path or url_for('index'))


@app.route('/logout')
def logout():
    logout_user()
    flash ('Successfully Logged Out', 'success')
    return redirect(url_for('index'))


@app.route('/login')
def login():
    next = request.args.get('next')
    from uuid import uuid1
    state = str(uuid1())
    session['oauth_state'] = state
    session['last_path'] = next

    r = Reddit(
        client_id=app.config['REDDIT_CLIENT_ID'],
        client_secret=app.config['REDDIT_CLIENT_SECRET'],
        redirect_uri=app.config['REDDIT_REDIRECT_URI'],
        user_agent=app.config['REDDIT_USER_AGENT'],
    )

    authorize_url = r.auth.url({'identity'}, state, duration='temporary')
    return redirect(authorize_url)


@app.route('/user/<nickname>')
@app.route('/user/<nickname>/')
@app.route('/user/<nickname>/<int:page>')
@app.route('/user/<nickname>/<int:page>/')
def user(nickname, page=1):
    user = user_by_nickname(nickname)
    if user is None:
        flash('User ' + nickname + ' not found.', 'warning')
        return redirect(url_for('index'))
    return render_template('user.html',
                           user=user,
                           title=nickname)


@app.route('/editprofile', methods=['GET', 'POST'])
@login_required
def edit():
    form = EditProfileForm()
    if form.validate_on_submit():
        g.user.emailReminders = form.emailReminders.data
        g.user.pmReminders = form.pmReminders.data
        if not form.email.data:
            g.user.email = None
            g.user.emailConfirmed = None
            db.session.add(g.user)
            db.session.commit()
            flash('Profile Successfully Updated.', 'info')
            return redirect(url_for('edit'))
        if form.email.data == g.user.email and g.user.emailConfirmed:
            db.session.add(g.user)
            db.session.commit()
            flash('Profile Successfully Updated.', 'info')
            return redirect(url_for('edit'))
        provisionalEmail = form.email.data
        if g.user.email is None or g.user.emailConfirmed == False:
            g.user.email = provisionalEmail
            g.user.emailConfirmed = False
            db.session.add(g.user)
            db.session.commit()
        message.send_email('Confirm Your Account', [provisionalEmail], 'confirmation',
            user=g.user, token=g.user.generate_confirmation_token(email=provisionalEmail))
        flash('A confirmation message has been sent to you. Please check your spam or junk folder.', 'warning')
        return redirect(url_for('edit'))

    form.email.data = g.user.email
    form.emailReminders.data = g.user.emailReminders
    form.pmReminders.data = g.user.pmReminders

    return render_template('editprofile.html',
                           form=form,
                           user=g.user)


@app.route('/confirm/<token>')
@login_required
def confirm(token):
    if current_user.confirm(token):
        flash('You have successfully confirmed your email address.  Thanks!', 'success')
    else:
        flash('The confirmation link is invalid or has expired.', 'danger')
    return redirect(url_for('index'))


@app.route('/confirm')
@login_required
def retry_confirm():
    if current_user.emailConfirmed:
        flash('Your email address has been confirmed.', 'success')
        return redirect(url_for('index'))
    token = current_user.generate_confirmation_token()
    message.send_email('Confirm Your Account', [current_user], 'confirmation', token=token)
    flash('A new confirmation email has been sent to you. Please check your spam or junk folder.', 'info')
    return redirect(url_for('index'))


@app.route('/teams')
def teams():
    teams = Team.query.all()
    return render_template('teams.html',
                           title='Teams',
                           teams=teams)


@app.route('/about')
def about():
    return render_template('about.html', title='About')


@app.route('/apply', methods=['GET', 'POST'])
@login_required
def apply():
    application = VoterApplication.query.filter_by(user_id=g.user.id).filter_by(season=app.config['SEASON']).first()
    if application:
        flash("Application Already Submitted", 'info')
        return redirect(url_for('index'))
    form = VoterApplicationForm()
    if form.validate_on_submit():
        application=VoterApplication(
            user_id = g.user.id,
            primary_team_id = form.primary_team_id.data.id,
            approach = form.approach.data,
            other_comments = form.other_comments.data,
            will_participate = form.will_participate.data,
            updated = datetime.utcnow(),
            season=app.config['SEASON']
        )
        for team in form.data['other_teams']:
            application.other_teams.append(team)
        for tag in form.data['consumption_tags']:
            application.consumption_tags.append(tag)
        db.session.add(application)
        db.session.commit()
        flash('Application submitted successfully!','success')
        return redirect(url_for('user', nickname=g.user.nickname))

    return render_template('apply.html',
                           title='Submit Application',
                           form=form)


@app.route('/users')
def users():
    if not current_user.is_admin():
        abort(403)
    users = User.query
    return render_template('users.html',
                           title='All Users',
                           users=users)


@app.route('/whatif')
def whatif():
    if not current_user.is_admin():
        abort(403)
    users = User.query.filter((User.is_voter == True) | (User.applicationFlag == True))
    return render_template('users.html',
                           title='What if Voters',
                           users=users)


@app.route('/_flag_user')
def _flag_user():
    if not current_user.is_admin():
        abort(403)
    id = request.args.get('id', False)
    if id:
        user = User.query.get(id)
        if user:
            flag = not user.applicationFlag
            user.applicationFlag = flag
            db.session.add(user)
            db.session.commit()
            return jsonify(flagged=flag)
    return jsonify()
