"""remove is_provisional from ballot table

Revision ID: 6a896d0e829
Revises: de507a7c103
Create Date: 2014-10-08 21:02:07.725604

"""

# revision identifiers, used by Alembic.
revision = '6a896d0e829'
down_revision = 'de507a7c103'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('ballot', 'is_provisional')
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('ballot', sa.Column('is_provisional', sa.BOOLEAN(), nullable=True))
    ### end Alembic commands ###