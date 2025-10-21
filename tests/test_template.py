# SPDX-FileCopyrightText: 2025 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from cinder_volume import template


class TestDirectory:
    """Test the Directory class."""

    def test_directory_creation(self):
        """Test creating a Directory instance."""
        dir_obj = template.Directory(path="/test/path", mode=0o755, location="common")
        assert dir_obj.path == Path("/test/path")
        assert dir_obj.mode == 0o755
        assert dir_obj.location == "common"

    def test_directory_default_values(self):
        """Test Directory with default values."""
        dir_obj = template.Directory(path="test/path")
        assert dir_obj.path == Path("test/path")
        assert dir_obj.mode == 0o750
        assert dir_obj.location == "common"


class TestCommonDirectory:
    """Test the CommonDirectory class."""

    def test_common_directory_creation(self):
        """Test creating a CommonDirectory instance."""
        dir_obj = template.CommonDirectory(path="/test/path", mode=0o755)
        assert dir_obj.path == Path("/test/path")
        assert dir_obj.mode == 0o755
        assert dir_obj.location == "common"


class TestDataDirectory:
    """Test the DataDirectory class."""

    def test_data_directory_creation(self):
        """Test creating a DataDirectory instance."""
        dir_obj = template.DataDirectory(path="/test/path", mode=0o755)
        assert dir_obj.path == Path("/test/path")
        assert dir_obj.mode == 0o755
        assert dir_obj.location == "data"


class TestTemplate:
    """Test the Template class."""

    def test_template_creation(self):
        """Test creating a Template instance."""
        tpl = template.Template(
            src="test.j2",
            dest=Path("/dest"),
            mode=0o644,
            template_name="custom.j2",
            location="common",
        )
        assert tpl.filename == "test.j2"
        assert tpl.dest == Path("/dest")
        assert tpl.mode == 0o644
        assert tpl.template_name == "custom.j2"
        assert tpl.location == "common"

    def test_template_default_values(self):
        """Test Template with default values."""
        tpl = template.Template(src="test.j2", dest=Path("/dest"))
        assert tpl.filename == "test.j2"
        assert tpl.dest == Path("/dest")
        assert tpl.mode == 0o640
        assert tpl.template_name is None
        assert tpl.location == "common"

    def test_template_rel_path(self):
        """Test the rel_path method."""
        tpl = template.Template(src="test.j2", dest=Path("/dest"))
        assert tpl.rel_path() == Path("/dest/test.j2")

    def test_template_rel_path_with_custom_name(self):
        """Test the rel_path method with custom template name."""
        tpl = template.Template(
            src="test.j2", dest=Path("/dest"), template_name="custom.j2"
        )
        assert tpl.rel_path() == Path("/dest/custom.j2")

    def test_template_method(self):
        """Test the template method."""
        tpl = template.Template(src="test.j2", dest=Path("/dest"))
        assert tpl.template() == "test.j2"

    def test_template_method_with_custom_name(self):
        """Test the template method with custom template name."""
        tpl = template.Template(
            src="test.j2", dest=Path("/dest"), template_name="custom.j2"
        )
        assert tpl.template() == "custom.j2"


class TestCommonTemplate:
    """Test the CommonTemplate class."""

    def test_common_template_creation(self):
        """Test creating a CommonTemplate instance."""
        tpl = template.CommonTemplate(src="test.j2", dest=Path("/dest"))
        assert tpl.filename == "test.j2"
        assert tpl.dest == Path("/dest")
        assert tpl.location == "common"


class TestDataTemplate:
    """Test the DataTemplate class."""

    def test_data_template_creation(self):
        """Test creating a DataTemplate instance."""
        tpl = template.DataTemplate(src="test.j2", dest=Path("/dest"))
        assert tpl.filename == "test.j2"
        assert tpl.dest == Path("/dest")
        assert tpl.location == "data"
