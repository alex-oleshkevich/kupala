import io
import pytest
from _pytest.monkeypatch import MonkeyPatch
from decimal import Decimal
from pathlib import Path

from kupala.dotenv import DotEnv, EnvError, InvalidEnvValueError


@pytest.fixture()
def dotenv_content() -> str:
    return """
INT_VALUE=1
FLOAT_VALUE=3.14
DECIMAL_VALUE=2.99
DATETIME_VALUE=2020-01-01 00:00
DATE_VALUE=2020-01-01
TIME_VALUE=23:59
LIST_VALUE=3.14,2.036,6.626
JSON_VALUE={"key": "value"}
TIMEDELTA_VAULE=60
BOOL_VALUE=true
URL_VALUE=https://username:password@example.com/path/
UUID_VALUE=d30513a2-3697-4bde-a43a-177c85c5a151
LOG_LEVEL_VALUE=INFO
PATH_VALUE=/tmp
ENUM_VALUE=/tmp
BOOLEAN_VALUE=true
DOMAIN=example.org
ADMIN_EMAIL=admin@${DOMAIN}
"""


@pytest.fixture()
def dotenv(dotenv_content: str) -> DotEnv:
    stream = io.StringIO(dotenv_content)
    return DotEnv([]).load(stream=stream)


def test_get(dotenv: DotEnv) -> None:
    assert dotenv.get('DOMAIN') == 'example.org'


def test_default_value(dotenv: DotEnv) -> None:
    assert dotenv.get('MISSING_KEY', 'default') == 'default'


def test_raises_for_missing_default(dotenv: DotEnv) -> None:
    with pytest.raises(EnvError) as ex:
        dotenv.get('MISSING_KEY')
    assert str(ex.value) == 'Environment variable "MISSING_KEY" is undefined and has no default.'


def test_raises_for_missing_file_var(dotenv: DotEnv) -> None:
    with pytest.raises(EnvError) as ex:
        dotenv.get('MISSING_KEY', check_file=True)
    assert str(ex.value) == (
        'Environment variable "MISSING_KEY" is undefined and has no default. '
        'Also, additional "MISSING_KEY_FILE" has been searched but is also undefined.'
    )


def test_lookups_file(dotenv: DotEnv, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    filename = f'{tmp_path}/file.secret'
    monkeypatch.setenv('SECRET_FILE', filename)
    with open(filename, 'w') as f:
        f.write('SECRET_VALUE')
    assert dotenv.get('SECRET', check_file=True) == 'SECRET_VALUE'


def test_raises_for_missing_file(dotenv: DotEnv, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv('MISSING_KEY_FILE', '/tmp/somefile!')
    with pytest.raises(EnvError) as ex:
        dotenv.get('MISSING_KEY', check_file=True)
    assert str(ex.value) == (
        'Environment variable "MISSING_KEY" is undefined and has no default. '
        'Also, the file /tmp/somefile! specified by "MISSING_KEY_FILE" variable does not exist.'
    )


def test_cast_function(dotenv: DotEnv) -> None:
    def caster(value: str) -> int:
        return int(value)

    assert dotenv.get('INT_VALUE', cast=caster) == 1


def test_validators(dotenv: DotEnv) -> None:
    def validator(value: int) -> bool:
        return value < 2

    assert dotenv.get('INT_VALUE', cast=int, validators=[validator]) == 1
    with pytest.raises(InvalidEnvValueError):
        dotenv.get('FLOAT_VALUE', cast=float, validators=[validator])


def test_int_value(dotenv: DotEnv) -> None:
    assert dotenv.int('INT_VALUE') == 1


def test_int_min_validator(dotenv: DotEnv) -> None:
    assert dotenv.int('INT_VALUE', min=1) == 1
    with pytest.raises(InvalidEnvValueError):
        dotenv.int('INT_VALUE', min=1, min_inclusive=False)


def test_int_max_validator(dotenv: DotEnv) -> None:
    assert dotenv.int('INT_VALUE', max=1) == 1
    with pytest.raises(InvalidEnvValueError):
        dotenv.int('INT_VALUE', max=1, max_inclusive=False)


def test_float_value(dotenv: DotEnv) -> None:
    assert dotenv.float('FLOAT_VALUE') == 3.14


def test_float_min_validator(dotenv: DotEnv) -> None:
    assert dotenv.float('FLOAT_VALUE', min=3.14) == 3.14
    with pytest.raises(InvalidEnvValueError):
        dotenv.float('FLOAT_VALUE', min=3.14, min_inclusive=False)


def test_float_max_validator(dotenv: DotEnv) -> None:
    assert dotenv.float('FLOAT_VALUE', max=3.14) == 3.14
    with pytest.raises(InvalidEnvValueError):
        dotenv.float('FLOAT_VALUE', max=3.14, max_inclusive=False)


def test_decimal_value(dotenv: DotEnv) -> None:
    assert dotenv.decimal('DECIMAL_VALUE') == Decimal('2.99')


def test_decimal_min_validator(dotenv: DotEnv) -> None:
    assert dotenv.decimal('DECIMAL_VALUE', min=Decimal('2.99')) == Decimal('2.99')
    with pytest.raises(InvalidEnvValueError):
        dotenv.decimal('DECIMAL_VALUE', min=Decimal('2.99'), min_inclusive=False)


def test_decimal_max_validator(dotenv: DotEnv) -> None:
    assert dotenv.decimal('DECIMAL_VALUE', max=Decimal('2.99')) == Decimal('2.99')
    with pytest.raises(InvalidEnvValueError):
        dotenv.decimal('DECIMAL_VALUE', max=Decimal('2.99'), max_inclusive=False)


def test_str_value(dotenv: DotEnv) -> None:
    assert dotenv.str('DOMAIN') == 'example.org'


def test_str_choices_validator_value(dotenv: DotEnv) -> None:
    with pytest.raises(InvalidEnvValueError):
        assert dotenv.str('DOMAIN', choices=['DOMAIN', 'SUBDOMAIN']) == 'example.org'
    assert dotenv.str('DOMAIN', choices=['example.org', 'domain.tld']) == 'example.org'


def test_bool_value(dotenv: DotEnv) -> None:
    assert dotenv.bool('BOOL_VALUE') is True


def test_list_value(dotenv: DotEnv) -> None:
    assert dotenv.list('LIST_VALUE', sub_cast=float) == [3.14, 2.036, 6.626]
