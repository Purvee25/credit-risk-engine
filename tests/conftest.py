"""
Test configuration.

Point the decision store at a throwaway SQLite file *before* `db` is imported,
so the suite never writes into the development database. Without this, running
pytest pollutes the running app with fixture applicants (T-API-*, T-MC-*).
"""

import os
import tempfile

_TEST_DB = os.path.join(tempfile.gettempdir(), "credit_risk_test.db")

# Must be set before `db` (and anything importing it) is first imported.
os.environ["CR_DATABASE_URL"] = f"sqlite:///{_TEST_DB}"


def pytest_sessionstart(session):
    """Start every run from an empty, initialised store."""
    if os.path.exists(_TEST_DB):
        os.remove(_TEST_DB)
    # TestClient only fires FastAPI's startup event inside a `with` block, so
    # create the schema explicitly — otherwise writes hit a table-less database.
    import db
    db.init_db()


def pytest_sessionfinish(session, exitstatus):
    if os.path.exists(_TEST_DB):
        os.remove(_TEST_DB)
