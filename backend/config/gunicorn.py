"""Render's small stateless instance: one shared quota ledger, two request threads."""

import os

if os.environ.get("APP_ENV", "production") != "production":
    raise RuntimeError("Gunicorn production start requires APP_ENV=production.")
os.environ.setdefault("APP_ENV", "production")
bind = "0.0.0.0:" + os.environ.get("PORT", "10000")
workers = 1
worker_class = "gthread"
threads = 2
timeout = 60  # Application deadline is 35s; allow response processing and shutdown margin.
graceful_timeout = 45
keepalive = 2
accesslog = "-"
errorlog = "-"
# U is the path without the query string; omit IP, referrer and user-agent as well.
access_log_format = "%(m)s %(U)s %(s)s %(L)s"
forwarded_allow_ips = ""  # Django's explicit TRUST_PROXY_SSL_HEADER controls TLS trust.
