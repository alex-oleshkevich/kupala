from __future__ import annotations

import math
import typing
from starlette.requests import HTTPConnection

M = typing.TypeVar("M")


def get_page_value(conn: HTTPConnection, param_name: str = "page") -> int:
    page = 1
    try:
        page = max(1, int(conn.query_params.get(param_name, 1)))
    except (TypeError, ValueError):
        pass
    return page


def get_page_size_value(
    conn: HTTPConnection,
    param_name: str = "page_size",
    max_page_size: int = 100,
    default: int = 20,
) -> int:
    try:
        page_size = int(conn.query_params.get(param_name, default))
        return min(page_size, max_page_size)
    except (TypeError, ValueError):
        return default


class Page(typing.Generic[M]):
    def __init__(self, rows: typing.Sequence[M], total_rows: int, page: int, page_size: int) -> None:
        self.rows = rows
        self.total_rows = total_rows
        self.page = page
        self.page_size = page_size
        self._pointer = 0

    @property
    def total_pages(self) -> int:
        """Total pages in the row set."""
        return math.ceil(self.total_rows / self.page_size)

    @property
    def has_next(self) -> bool:
        """Test if the next page is available."""
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        """Test if the previous page is available."""
        return self.page > 1

    @property
    def has_other(self) -> bool:
        """Test if page has next or previous pages."""
        return self.has_next or self.has_previous

    @property
    def next_page(self) -> int:
        """
        Next page number.

        Always returns an integer. If there is no more pages the current page number returned.
        """
        return min(self.total_pages, self.page + 1)

    @property
    def previous_page(self) -> int:
        """
        Previous page number.

        Always returns an integer. If there is no previous page, the number 1 returned.
        """
        return max(1, self.page - 1)

    @property
    def start_index(self) -> int:
        """The 1-based index of the first item on this page."""
        if self.page == 1:
            return 1
        return (self.page - 1) * self.page_size + 1

    @property
    def end_index(self) -> int:
        """The 1-based index of the last item on this page."""
        return min(self.start_index + self.page_size - 1, self.total_rows)

    def iter_pages(
        self, left_edge: int = 3, left_current: int = 3, right_current: int = 3, right_edge: int = 3
    ) -> typing.Generator[int | None, None, None]:
        pages_end = self.total_pages + 1

        if pages_end == 1:
            return

        left_end = min(1 + left_edge, pages_end)
        yield from range(1, left_end)

        if left_end == pages_end:
            return

        mid_start = max(left_end, self.page - left_current)
        mid_end = min(self.page + right_current + 1, pages_end)

        if mid_start - left_end > 0:
            yield None

        yield from range(mid_start, mid_end)

        if mid_end == pages_end:
            return

        right_start = max(mid_end, pages_end - right_edge)

        if right_start - mid_end > 0:
            yield None

        yield from range(right_start, pages_end)

    def __iter__(self) -> typing.Iterator[M]:
        return iter(self.rows)

    def __next__(self) -> M:
        if self._pointer == len(self.rows):
            raise StopIteration
        self._pointer += 1
        return self.rows[self._pointer - 1]

    def __getitem__(self, item: int) -> M:
        return self.rows[item]

    def __len__(self) -> int:
        return len(self.rows)

    def __bool__(self) -> bool:
        return len(self.rows) > 0

    def __str__(self) -> str:
        return (
            f"Page {self.page} of {self.total_pages}, rows {self.start_index} - {self.end_index} of {self.total_rows}."
        )

    def __repr__(self) -> str:
        return f"<Page: page={self.page}, total_pages={self.total_pages}>"
