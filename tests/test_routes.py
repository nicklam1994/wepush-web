"""Tests for WePush Web routes."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root is on sys.path
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

# Disable auth middleware
os.environ["WEPUSH_AUTH_TOKEN"] = ""

# Patch init_scheduler BEFORE importing anything that triggers it
import scheduler as _scheduler_mod
_scheduler_mod.init_scheduler = lambda: None

# Now safe to import main
from main import app
from fastapi.testclient import TestClient

import database
import models  # noqa: ensure models are imported

# Use a temporary in-memory SQLite for tests
_test_db_path = os.path.join(tempfile.gettempdir(), "test_wepush.db")

# Override engine with in-memory SQLite
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_test_engine = create_engine(
    f"sqlite:///{_test_db_path}",
    connect_args={"check_same_thread": False},
    echo=False,
)
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)

# Replace the app's DB dependency
def _override_get_db():
    db = _TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[database.get_db] = _override_get_db


def setup_module():
    """Create all tables in the test database."""
    database.Base.metadata.create_all(bind=_test_engine)


def teardown_module():
    """Clean up test database."""
    database.Base.metadata.drop_all(bind=_test_engine)
    if os.path.exists(_test_db_path):
        os.remove(_test_db_path)


client = TestClient(app)


class TestDashboard:
    """Tests for the dashboard/index page."""

    def test_index_returns_200(self):
        response = client.get("/")
        assert response.status_code == 200
        assert "WePush" in response.text

    def test_index_contains_dashboard_content(self):
        response = client.get("/")
        assert response.status_code == 200
        assert "儀表板" in response.text or "dashboard" in response.text.lower()


class TestSettings:
    """Tests for the settings page."""

    def test_settings_page(self):
        response = client.get("/settings")
        assert response.status_code == 200
        assert "帳號設置" in response.text or "settings" in response.text.lower()


class TestTemplates:
    """Tests for template management pages."""

    def test_template_list(self):
        response = client.get("/templates")
        assert response.status_code == 200
        assert "模板" in response.text

    def test_template_new(self):
        response = client.get("/templates/new")
        assert response.status_code == 200
        assert "模板" in response.text


class TestRecipients:
    """Tests for recipient management pages."""

    def test_recipient_list(self):
        response = client.get("/recipients")
        assert response.status_code == 200
        assert "接收人" in response.text


class TestTasks:
    """Tests for scheduled task pages."""

    def test_task_list(self):
        response = client.get("/tasks")
        assert response.status_code == 200
        assert "定時任務" in response.text or "task" in response.text.lower()


class TestPush:
    """Tests for manual push page."""

    def test_push_page(self):
        response = client.get("/push")
        assert response.status_code == 200
        assert "推送" in response.text


class TestHistory:
    """Tests for push history pages."""

    def test_history_list(self):
        response = client.get("/history")
        assert response.status_code == 200
        assert "歷史" in response.text or "history" in response.text.lower()


class TestStaticFiles:
    """Tests for static file serving."""

    def test_style_css_served(self):
        response = client.get("/static/style.css")
        assert response.status_code == 200
        assert "body" in response.text
        assert "background" in response.text
