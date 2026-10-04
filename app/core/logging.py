import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging once for the whole application."""
    root = logging.getLogger()
    root.setLevel(level.upper())

    # Avoid duplicate handlers when the app is reloaded or created in tests.
    if root.handlers:
        root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)
