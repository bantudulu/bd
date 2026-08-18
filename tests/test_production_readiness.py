import os
import subprocess
import sys

import pytest

from app.schema_migrations import LATEST_SCHEMA_VERSION, assert_schema_current, current_schema_version, run_migrations


@pytest.mark.asyncio
async def test_versioned_migration_baselines_existing_schema():
    assert await current_schema_version() == 0
    version = await run_migrations()
    assert version == LATEST_SCHEMA_VERSION
    assert await current_schema_version() == LATEST_SCHEMA_VERSION
    assert await assert_schema_current() == LATEST_SCHEMA_VERSION


@pytest.mark.asyncio
async def test_health_endpoints(client):
    live = await client.get("/health/live")
    assert live.status_code == 200
    assert live.json()["status"] == "live"

    ready = await client.get("/health/ready")
    assert ready.status_code == 200
    body = ready.json()
    assert body["status"] == "ready"
    assert body["schema_version"] == LATEST_SCHEMA_VERSION


def _config_import_result(extra_env: dict[str, str]):
    env = os.environ.copy()
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", "import app.config"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_production_rejects_sqlite():
    result = _config_import_result(
        {
            "APP_ENV": "production",
            "ENABLE_DEV_SEED": "false",
            "SECRET_KEY": "production-secret-key-longer-than-thirty-two-chars",
            "DATABASE_URL": "sqlite+aiosqlite:///./unsafe-production.db",
        }
    )
    assert result.returncode != 0
    assert "SQLite tidak diizinkan" in result.stderr


def test_production_rejects_dev_seed():
    result = _config_import_result(
        {
            "APP_ENV": "production",
            "ENABLE_DEV_SEED": "true",
            "SECRET_KEY": "production-secret-key-longer-than-thirty-two-chars",
            "DATABASE_URL": "mysql+aiomysql://user:pass@127.0.0.1/bantudulu",
        }
    )
    assert result.returncode != 0
    assert "ENABLE_DEV_SEED" in result.stderr
