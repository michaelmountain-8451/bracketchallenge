from cbbpoll import app, db, bot
from models import User, Team
from decorators import async

def team_by_flair(flair):
    return Team.query.filter_by(flair = flair).first()

@async
def update_flair(user, redditor):
    return user
