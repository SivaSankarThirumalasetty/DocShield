"""Test environment: isolated SQLite DB and a test-only officer key.

These must be set before any backend module is imported, because settings and
the storage singleton are created at import time.
"""
import os
import tempfile

_tmpdir = tempfile.mkdtemp(prefix="docshield-tests-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.join(_tmpdir, 'test.db')}")
os.environ.setdefault("DOCSHIELD_OFFICER_KEY", "test-only-officer-key")
os.environ.setdefault("PERSISTENCE_MODE", "sqlite")
os.environ.setdefault("RATE_LIMIT_ANALYZE_PER_MINUTE", "1000")
