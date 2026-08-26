"""Add organizations and tenant scoping

Revision ID: 5929970f87eb
Revises: 
Create Date: 2026-08-25 20:13:57.509273

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
import secrets
from datetime import datetime, timezone


# revision identifiers, used by Alembic.
revision: str = '5929970f87eb'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create organizations table
    op.create_table('organizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('invite_code', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_organizations_invite_code'), 'organizations', ['invite_code'], unique=True)
    
    # 2. Insert default legacy organization
    orgs_table = table('organizations',
        column('id', sa.Integer),
        column('name', sa.String),
        column('invite_code', sa.String),
        column('created_at', sa.DateTime),
        column('updated_at', sa.DateTime)
    )
    
    op.bulk_insert(orgs_table, [
        {
            'id': 1,
            'name': 'Legacy Organization',
            'invite_code': secrets.token_urlsafe(16),
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc)
        }
    ])
    
    # 3. Add organization_id to existing tables using batch operations to support SQLite
    
    with op.batch_alter_table('campaigns') as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), server_default='1', nullable=False))
        batch_op.create_foreign_key('fk_campaigns_org', 'organizations', ['organization_id'], ['id'])
        
    with op.batch_alter_table('approvals') as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), server_default='1', nullable=False))
        batch_op.create_foreign_key('fk_approvals_org', 'organizations', ['organization_id'], ['id'])
        
    with op.batch_alter_table('automation_events') as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), server_default='1', nullable=False))
        batch_op.create_foreign_key('fk_automation_events_org', 'organizations', ['organization_id'], ['id'])
        
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), server_default='1', nullable=False))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False))
        batch_op.create_foreign_key('fk_users_org', 'organizations', ['organization_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('fk_users_org', type_='foreignkey')
        batch_op.drop_column('updated_at')
        batch_op.drop_column('organization_id')
        
    with op.batch_alter_table('automation_events') as batch_op:
        batch_op.drop_constraint('fk_automation_events_org', type_='foreignkey')
        batch_op.drop_column('organization_id')
        
    with op.batch_alter_table('approvals') as batch_op:
        batch_op.drop_constraint('fk_approvals_org', type_='foreignkey')
        batch_op.drop_column('organization_id')
        
    with op.batch_alter_table('campaigns') as batch_op:
        batch_op.drop_constraint('fk_campaigns_org', type_='foreignkey')
        batch_op.drop_column('organization_id')
        
    op.drop_index(op.f('ix_organizations_invite_code'), table_name='organizations')
    op.drop_table('organizations')
