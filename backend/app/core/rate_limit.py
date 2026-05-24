from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Rate limiting is disabled by default (RATELIMIT_ENABLED=False).
# To enable, set RATELIMIT_ENABLED=true in .env and optionally tune RATELIMIT_DEFAULT.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],          # No default limits — per-endpoint decorators still work when enabled
    storage_uri="memory://",
    strategy="fixed-window",
    enabled=False,              # Disabled — flip to True or set RATELIMIT_ENABLED=true to activate
)
