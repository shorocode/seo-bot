from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), nullable=False, comment='شناسه کاربر در تلگرام'),
        sa.Column('username', sa.String(length=100), nullable=True, comment='نام کاربری تلگرام'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False, comment='تاریخ ایجاد'),
        sa.PrimaryKeyConstraint('id'),
        comment='جدول کاربران سیستم'
    )
    
    op.create_table(
        'analysis_results',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='شناسه رکورد'),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='شناسه کاربر'),
        sa.Column('tool_id', sa.String(length=100), nullable=False, comment='نوع ابزار تحلیل'),
        sa.Column('result', sa.Text(), nullable=False, comment='نتیجه تحلیل'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False, comment='تاریخ ایجاد'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='نتایج تحلیل‌های انجام شده'
    )
    
    # ایجاد ایندکس‌ها
    op.create_index(op.f('ix_analysis_results_user_id'), 'analysis_results', ['user_id'], unique=False)
    op.create_index(op.f('ix_analysis_results_created_at'), 'analysis_results', ['created_at'], unique=False)

def downgrade():
    # حذف ایندکس‌ها اول
    op.drop_index(op.f('ix_analysis_results_created_at'), table_name='analysis_results')
    op.drop_index(op.f('ix_analysis_results_user_id'), table_name='analysis_results')
    
    # سپس حذف جداول
    op.drop_table('analysis_results')
    op.drop_table('users')
