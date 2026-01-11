"""
Alembic migration for subscription & billing system
Run with: alembic upgrade head
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    # Create plans table
    op.create_table(
        'plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('base_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('setup_fee', sa.Numeric(precision=10, scale=2), nullable=True, server_default='0'),
        sa.Column('billing_interval', sa.String(), nullable=True, server_default='monthly'),
        sa.Column('max_features', sa.Integer(), nullable=True),
        sa.Column('trial_days', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )

    # Create features table
    op.create_table(
        'features',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('feature_type', sa.String(), nullable=False),
        sa.Column('default_limit', sa.Integer(), nullable=True),
        sa.Column('standalone_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('customizable', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('display_order', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
        sa.CheckConstraint("feature_type IN ('boolean', 'quota', 'unlimited')")
    )

    # Create plan_features table
    op.create_table(
        'plan_features',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('feature_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('limit_override', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['feature_id'], ['features.id']),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plan_id', 'feature_id')
    )

    # Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('base_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('addons_price', sa.Numeric(precision=10, scale=2), nullable=True, server_default='0'),
        sa.Column('discount_amount', sa.Numeric(precision=10, scale=2), nullable=True, server_default='0'),
        sa.Column('tax_amount', sa.Numeric(precision=10, scale=2), nullable=True, server_default='0'),
        sa.Column('total_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('billing_period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('billing_period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('trial_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stripe_customer_id', sa.String(), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(), nullable=True),
        sa.Column('stripe_current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stripe_current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stripe_cancel_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'stripe_subscription_id'),
        sa.CheckConstraint("status IN ('trialing', 'active', 'past_due', 'cancelled')")
    )

    # Create subscription_addons table
    op.create_table(
        'subscription_addons',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('feature_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('limit_override', sa.Integer(), nullable=True),
        sa.Column('price_override', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('added_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['feature_id'], ['features.id']),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('subscription_id', 'feature_id')
    )

    # Create discounts table
    op.create_table(
        'discounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('discount_type', sa.String(), nullable=False),
        sa.Column('discount_value', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('applies_to', sa.String(), nullable=False),
        sa.Column('max_redemptions', sa.Integer(), nullable=True),
        sa.Column('current_redemptions', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        sa.CheckConstraint("discount_type IN ('percentage', 'fixed')"),
        sa.CheckConstraint("applies_to IN ('subscription', 'addon', 'all')")
    )

    # Create subscription_discounts table
    op.create_table(
        'subscription_discounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('discount_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('addon_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['addon_id'], ['subscription_addons.id']),
        sa.ForeignKeyConstraint(['discount_id'], ['discounts.id']),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('subscription_id', 'discount_id', 'addon_id')
    )

    # Create feature_usage table
    op.create_table(
        'feature_usage',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('feature_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('billing_period_id', sa.String(), nullable=False),
        sa.Column('usage_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('limit_amount', sa.Integer(), nullable=True),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reset_warning_sent', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('exceeded_notification_sent', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['feature_id'], ['features.id']),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'feature_id', 'billing_period_id')
    )

    # Create indexes for better query performance
    op.create_index('idx_subscriptions_org_id', 'subscriptions', ['org_id'])
    op.create_index('idx_subscriptions_status', 'subscriptions', ['status'])
    op.create_index('idx_subscriptions_stripe_id', 'subscriptions', ['stripe_subscription_id'])
    op.create_index('idx_subscription_addons_subscription_id', 'subscription_addons', ['subscription_id'])
    op.create_index('idx_discounts_code', 'discounts', ['code'])
    op.create_index('idx_feature_usage_org_id', 'feature_usage', ['org_id'])
    op.create_index('idx_feature_usage_period', 'feature_usage', ['org_id', 'billing_period_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_feature_usage_period')
    op.drop_index('idx_feature_usage_org_id')
    op.drop_index('idx_discounts_code')
    op.drop_index('idx_subscription_addons_subscription_id')
    op.drop_index('idx_subscriptions_stripe_id')
    op.drop_index('idx_subscriptions_status')
    op.drop_index('idx_subscriptions_org_id')
    
    # Drop tables
    op.drop_table('feature_usage')
    op.drop_table('subscription_discounts')
    op.drop_table('discounts')
    op.drop_table('subscription_addons')
    op.drop_table('subscriptions')
    op.drop_table('plan_features')
    op.drop_table('features')
    op.drop_table('plans')
