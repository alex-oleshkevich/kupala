import types

import pytest

from kupala.utils import import_string

variable_to_import = True


class TestImportString:
    def test_imports_using_string(self):
        var = import_string("tests.test_utils.variable_to_import")
        assert var == variable_to_import

    def test_returns_argument_if_not_string(self):
        a = 1
        var = import_string(a)
        assert var == a

    def test_raises_if_no_attribute(self):
        with pytest.raises(ImportError):
            import_string("tests.test_utils.invalid_import")

    def test_raises_if_string_malformed(self):
        with pytest.raises(ImportError):
            import_string("tests.test_utils.")

    def test_imports_module(self):
        var = import_string("tests")
        assert isinstance(var, types.ModuleType)
