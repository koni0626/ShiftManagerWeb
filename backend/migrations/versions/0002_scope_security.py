"""Tenant row security and membership period integrity."""

from alembic import op

revision = "0002_scope_security"
down_revision = "719d581ab8d4"
branch_labels = None
depends_on = None
TABLES = (
    "branches",
    "staff",
    "memberships",
    "services",
    "clients",
    "client_branches",
    "visits",
    "assignments",
    "publications",
    "duties",
    "request_windows",
    "submissions",
    "notices",
    "history",
    "pay_terms",
    "geocode_jobs",
)


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        "ALTER TABLE memberships ADD CONSTRAINT membership_period_exclusion EXCLUDE USING gist (staff_id WITH =, branch_id WITH =, daterange(valid_from, valid_until, '[]') WITH &&)"
    )
    for table in TABLES:
        predicate = "(scope_id = current_setting('app.scope_id', true) OR current_setting('app.role', true) = 'system_admin')"
        read = (
            predicate
            if table != "staff"
            else f"({predicate} OR user_id = current_setting('app.user_id', true))"
        )
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY scope_isolation ON {table} USING ({read}) WITH CHECK ({predicate})"
        )
    # Deployment may use a differently named role; see scripts/grant_db.py.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='atelier_app') THEN GRANT USAGE ON SCHEMA public TO atelier_app; GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO atelier_app; REVOKE ALL ON alembic_version FROM atelier_app; END IF; END $$"
    )


def downgrade():
    for table in TABLES:
        op.execute(f"DROP POLICY scope_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memberships DROP CONSTRAINT membership_period_exclusion")
