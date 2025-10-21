# SPDX-FileCopyrightText: 2025 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

import logging
import tempfile
from pathlib import Path

from cinder_volume import log


class TestSetupLogging:
    """Test the setup_logging function."""

    def test_setup_logging_with_path(self):
        """Test setup_logging with a Path object."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            logfile = Path(tmp.name)

        try:
            # Clear existing handlers to ensure clean test
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            root_logger.handlers.clear()

            log.setup_logging(logfile)

            # Check that a handler was added to the root logger
            handlers = root_logger.handlers
            assert len(handlers) > 0

            # Check that the handler is a FileHandler with the correct file
            file_handler = None
            for handler in handlers:
                if isinstance(handler, logging.FileHandler):
                    file_handler = handler
                    break

            assert file_handler is not None
            assert file_handler.baseFilename == str(logfile)
        finally:
            # Restore original handlers
            root_logger = logging.getLogger()
            root_logger.handlers = original_handlers
            # Clean up
            logfile.unlink(missing_ok=True)

    def test_setup_logging_with_string(self):
        """Test setup_logging with a string path."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            logfile = tmp.name

        try:
            # Clear existing handlers to ensure clean test
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            root_logger.handlers.clear()

            log.setup_logging(logfile)

            # Check that a handler was added to the root logger
            handlers = root_logger.handlers
            assert len(handlers) > 0
        finally:
            # Restore original handlers
            root_logger = logging.getLogger()
            root_logger.handlers = original_handlers
            # Clean up
            Path(logfile).unlink(missing_ok=True)
