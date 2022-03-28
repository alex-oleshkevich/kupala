from __future__ import annotations

import math
import typing

M = typing.TypeVar('M')


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

        Always returns an integer. If there is no more pages the current page
        number returned.
        """
        return min(self.total_pages, self.page + 1)

    @property
    def previous_page(self) -> int:
        """
        Previous page number.

        Always returns an integer. If there is no previous page, the number 1
        returned.
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
        last = 0
        for number in range(1, self.total_pages + 1):
            if (
                number <= left_edge
                or (number >= self.page - left_current - 1 and number < self.page + right_current)
                or number > self.total_pages - right_edge
            ):
                if last + 1 != number:
                    yield None
                yield number
                last = number

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
            f'Page {self.page} of {self.total_pages}, rows {self.start_index} - {self.end_index} of {self.total_rows}.'
        )

    def __repr__(self) -> str:
        return f'<Page: page={self.page}, total_pages={self.total_pages}>'
