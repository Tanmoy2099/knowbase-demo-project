import os
from dataclasses import dataclass, field


class ImproperlyConfigured(Exception):
    pass


@dataclass
class Config:
    SECRET_KEY: str
    FLASK_ENV: str = "production"
    DEBUG: bool = False
    TESTING: bool = False

    SQLALCHEMY_DATABASE_URI: str = ""
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ECHO: bool = False

    AI_PROVIDER: str = "openai"
    OPENAI_API_KEY: str = ""
    MISTRAL_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://ollama:11434"

    N8N_BASE_URL: str = "http://n8n:5678"
    N8N_API_KEY: str = ""
    N8N_WEBHOOK_SECRET: str = ""

    CORS_ORIGIN: str = "http://localhost:3000"
    RATE_LIMIT_STORAGE_URI: str = "memory://"

    MAX_CONTENT_LENGTH: int = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER: str = "/app/uploads"

    @classmethod
    def from_env(cls) -> "Config":
        required = ["SECRET_KEY", "POSTGRES_PASSWORD", "N8N_WEBHOOK_SECRET"]
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            raise ImproperlyConfigured(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        pg_host = os.environ.get("POSTGRES_HOST", "postgres")
        pg_port = os.environ.get("POSTGRES_PORT", "5432")
        pg_db = os.environ.get("POSTGRES_DB", "knowbase")
        pg_user = os.environ.get("POSTGRES_USER", "knowbase")
        pg_pass = os.environ["POSTGRES_PASSWORD"]

        flask_env = os.environ.get("FLASK_ENV", "production")

        return cls(
            SECRET_KEY=os.environ["SECRET_KEY"],
            FLASK_ENV=flask_env,
            DEBUG=flask_env == "development",
            SQLALCHEMY_DATABASE_URI=(
                f"postgresql+psycopg2://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
            ),
            SQLALCHEMY_ECHO=flask_env == "development",
            AI_PROVIDER=os.environ.get("AI_PROVIDER", "openai"),
            OPENAI_API_KEY=os.environ.get("OPENAI_API_KEY", ""),
            MISTRAL_API_KEY=os.environ.get("MISTRAL_API_KEY", ""),
            OLLAMA_BASE_URL=os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434"),
            N8N_BASE_URL=os.environ.get("N8N_BASE_URL", "http://n8n:5678"),
            N8N_API_KEY=os.environ.get("N8N_API_KEY", ""),
            N8N_WEBHOOK_SECRET=os.environ["N8N_WEBHOOK_SECRET"],
            CORS_ORIGIN=os.environ.get("CORS_ORIGIN", "http://localhost:3000"),
        )

    @classmethod
    def for_testing(cls) -> "Config":
        return cls(
            SECRET_KEY="test-secret-key-for-testing-only",
            FLASK_ENV="testing",
            TESTING=True,
            DEBUG=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_ECHO=False,
            N8N_WEBHOOK_SECRET="test-webhook-secret",
            AI_PROVIDER="openai",
            OPENAI_API_KEY="test-key",
        )
