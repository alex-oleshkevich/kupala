from unittest import mock

import pytest

from kupala.utils import call_as_async
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


@pytest.mark.asyncio
async def test_call_as_coroutine():
    mock1 = mock.MagicMock()
    mock2 = mock.MagicMock()

    arg1 = 1
    arg2 = 1

    def _fn(a, b):
        mock1(a, b)

    async def _afn(a, b):
        mock2(a, b)

    await call_as_async(_fn, arg1, b=arg2)
    await call_as_async(_afn, arg1, b=arg2)
    mock1.assert_called_once_with(arg1, arg2)
    mock2.assert_called_once_with(arg1, arg2)
