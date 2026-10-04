import logging

from app.core.logging import setup_logging


def test_setup_logging_sets_level_and_single_handler():
    setup_logging("DEBUG")
    setup_logging("DEBUG")  # calling twice must not duplicate handlers

    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) == 1
