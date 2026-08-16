import os
import pytest


@pytest.fixture(autouse=True)
def isolate_catalog_db_env():
    """Ensure HEALTHAI_CATALOG_DB environment variable is isolated per test."""
    original_db = os.environ.get("HEALTHAI_CATALOG_DB")
    yield
    if original_db is not None:
        os.environ["HEALTHAI_CATALOG_DB"] = original_db
    else:
        os.environ.pop("HEALTHAI_CATALOG_DB", None)
