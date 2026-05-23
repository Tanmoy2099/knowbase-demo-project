import pytest
import os
from app.core.config import Config, ImproperlyConfigured


def test_for_testing_returns_valid_config():
    config = Config.for_testing()
    assert config.SECRET_KEY == "test-secret-key-for-testing-only"
    assert config.TESTING is True
    assert "sqlite" in config.SQLALCHEMY_DATABASE_URI


def test_from_env_raises_on_missing_required_vars(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("N8N_WEBHOOK_SECRET", raising=False)
    with pytest.raises(ImproperlyConfigured) as exc:
        Config.from_env()
    assert "SECRET_KEY" in str(exc.value)


def test_from_env_raises_when_only_secret_key_missing(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("POSTGRES_PASSWORD", "test-pass")
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", "test-secret")
    with pytest.raises(ImproperlyConfigured) as exc:
        Config.from_env()
    assert "SECRET_KEY" in str(exc.value)


def test_from_env_raises_when_only_postgres_password_missing(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-key")
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", "test-secret")
    with pytest.raises(ImproperlyConfigured) as exc:
        Config.from_env()
    assert "POSTGRES_PASSWORD" in str(exc.value)


def test_from_env_raises_when_only_n8n_secret_missing(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-key")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test-pass")
    monkeypatch.delenv("N8N_WEBHOOK_SECRET", raising=False)
    with pytest.raises(ImproperlyConfigured) as exc:
        Config.from_env()
    assert "N8N_WEBHOOK_SECRET" in str(exc.value)


def test_from_env_builds_database_uri(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-key")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test-pass")
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("POSTGRES_HOST", "myhost")
    monkeypatch.setenv("POSTGRES_DB", "mydb")
    monkeypatch.setenv("POSTGRES_USER", "myuser")

    config = Config.from_env()
    assert "myhost" in config.SQLALCHEMY_DATABASE_URI
    assert "mydb" in config.SQLALCHEMY_DATABASE_URI
    assert "myuser" in config.SQLALCHEMY_DATABASE_URI
    assert "test-pass" in config.SQLALCHEMY_DATABASE_URI


def test_from_env_database_uri_contains_all_parts(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "key")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ssw0rd")
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", "sec")
    monkeypatch.setenv("POSTGRES_HOST", "db.example.com")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_DB", "testdb")
    monkeypatch.setenv("POSTGRES_USER", "dbuser")

    config = Config.from_env()
    uri = config.SQLALCHEMY_DATABASE_URI
    assert "postgresql+psycopg2" in uri
    assert "db.example.com" in uri
    assert "5433" in uri
    assert "testdb" in uri
    assert "dbuser" in uri


def test_ai_provider_defaults_to_openai(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "k")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", "s")
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    config = Config.from_env()
    assert config.AI_PROVIDER == "openai"


def test_ai_provider_reads_from_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "k")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", "s")
    monkeypatch.setenv("AI_PROVIDER", "mistral")
    config = Config.from_env()
    assert config.AI_PROVIDER == "mistral"


def test_for_testing_sets_n8n_webhook_secret():
    config = Config.for_testing()
    assert config.N8N_WEBHOOK_SECRET == "test-webhook-secret"


def test_for_testing_sets_flask_env_to_testing():
    config = Config.for_testing()
    assert config.FLASK_ENV == "testing"


def test_for_testing_enables_debug():
    config = Config.for_testing()
    assert config.DEBUG is True


def test_from_env_defaults_postgres_host_when_unset(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "k")
    monkeypatch.setenv("POSTGRES_PASSWORD", "pw")
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", "s")
    monkeypatch.delenv("POSTGRES_HOST", raising=False)
    monkeypatch.delenv("POSTGRES_DB", raising=False)
    monkeypatch.delenv("POSTGRES_USER", raising=False)
    config = Config.from_env()
    # Defaults: host=postgres, db=knowbase, user=knowbase
    assert "postgres" in config.SQLALCHEMY_DATABASE_URI
    assert "knowbase" in config.SQLALCHEMY_DATABASE_URI
