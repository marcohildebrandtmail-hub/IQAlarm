"""Schema compatibility across HA's voluptuous-to-probatio migration."""

try:
    import probatio as vol
except ImportError:
    import voluptuous as vol

__all__ = ["vol"]
