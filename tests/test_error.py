# SPDX-FileCopyrightText: 2025 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

from cinder_volume import error


class TestCinderError:
    """Test the CinderError exception class."""

    def test_cinder_error_creation(self):
        """Test creating a CinderError instance."""
        err = error.CinderError("Test error message")
        assert str(err) == "Test error message"
        assert isinstance(err, Exception)

    def test_cinder_error_inheritance(self):
        """Test that CinderError inherits from Exception."""
        assert issubclass(error.CinderError, Exception)

    def test_cinder_error_with_args(self):
        """Test CinderError with additional arguments."""
        err = error.CinderError("Error with args", "arg1", "arg2")
        assert str(err) == "('Error with args', 'arg1', 'arg2')"
