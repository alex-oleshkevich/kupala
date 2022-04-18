"""
Date, time, numbers, and currency formatters.

This module inspired/based on Flask-Babel.
"""
import datetime
import typing
from babel import dates, numbers

from kupala.i18n.locale import get_locale
from kupala.i18n.timezone import get_timezone, to_user_timezone

_DateTimeFormats = typing.Literal['short', 'medium', 'long', 'full']
_TimeDeltaFormats = typing.Literal['narrow', 'short', 'long']


def format_datetime(dt: datetime.datetime, format: _DateTimeFormats = 'medium', rebase: bool = True) -> str:
    locale = get_locale()
    if rebase:
        dt = to_user_timezone(dt)
    return dates.format_datetime(dt, format=format, locale=locale)


def format_date(date: datetime.datetime, format: _DateTimeFormats = 'medium') -> str:
    locale = get_locale()
    return dates.format_date(date, format=format, locale=locale)


def format_time(time: datetime.datetime, format: _DateTimeFormats = 'medium', rebase: bool = True) -> str:
    locale = get_locale()
    if rebase:
        time = to_user_timezone(time)
    return dates.format_time(time, format=format, locale=locale)


def format_timedelta(
    timedelta: datetime.timedelta,
    granularity: str = 'second',
    threshold: float = 0.85,
    add_direction: bool = False,
    format: _TimeDeltaFormats = 'long',
) -> str:
    locale = get_locale()
    return dates.format_timedelta(
        timedelta,
        granularity=granularity,
        format=format,
        locale=locale,
        threshold=threshold,
        add_direction=add_direction,
    )


def format_interval(
    start: typing.Union[datetime.datetime, datetime.date, datetime.time],
    end: typing.Union[datetime.datetime, datetime.date, datetime.time],
    skeleton: str | None = None,
    fuzzy: bool = True,
    rebase: bool = True,
) -> str:
    assert type(start) == type(end), '"start" and "end" arguments must be of the same type.'
    locale = get_locale()
    extra_kwargs = {}
    if rebase:
        extra_kwargs['tzinfo'] = get_timezone()
    return dates.format_interval(start, end, skeleton=skeleton, fuzzy=fuzzy, locale=locale, **extra_kwargs)


def format_number(number: float, decimal_quantization: bool = True, group_separator: bool = True) -> str:
    locale = get_locale()
    return numbers.format_decimal(
        number,
        locale=locale,
        decimal_quantization=decimal_quantization,
        group_separator=group_separator,
    )


def format_currency(
    number: float,
    currency: str,
    format: str = None,
    currency_digits: bool = True,
    format_type: str = 'standard',
    decimal_quantization: bool = True,
    group_separator: bool = True,
) -> str:
    locale = get_locale()
    return numbers.format_currency(
        number,
        currency,
        format=format,
        locale=locale,
        currency_digits=currency_digits,
        format_type=format_type,
        decimal_quantization=decimal_quantization,
        group_separator=group_separator,
    )


def format_percent(
    number: float, format: str = None, decimal_quantization: bool = True, group_separator: bool = True
) -> str:
    locale = get_locale()
    return numbers.format_percent(
        number,
        format=format,
        locale=locale,
        decimal_quantization=decimal_quantization,
        group_separator=group_separator,
    )


def format_scientific(number: float, format: str = None, decimal_quantization: bool = True) -> str:
    locale = get_locale()
    return numbers.format_scientific(number, format=format, decimal_quantization=decimal_quantization, locale=locale)
