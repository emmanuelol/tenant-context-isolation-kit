"""
Resilient Client Wrappers and Isolated Client Registry.
======================================================
Provides SafeClient, SafeSpreadsheet, and SafeWorksheet with automatic Tenacity exponential
retries for transient network/socket glitches, fast-fail execution modes, and an
IsolatedClientRegistry that guarantees zero cross-tenant credential bleed.
"""
from __future__ import annotations

import os
import socket
import threading
import logging
from typing import Callable, Any, Optional, Tuple
import urllib3.exceptions
from requests.exceptions import ConnectionError, ReadTimeout, RequestException
from tenacity import (
    retry,
    wait_exponential,
    retry_if_exception_type,
    retry_if_not_exception_type,
    retry_all,
    stop_after_attempt,
    stop_after_delay,
)
import gspread
import gspread.exceptions

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (
    gspread.exceptions.APIError,
    gspread.exceptions.GSpreadException,
    RequestException,
    urllib3.exceptions.HTTPError,
    socket.timeout,
    TimeoutError,
    ConnectionError,
    ReadTimeout,
    ConnectionResetError,
    BrokenPipeError,
    ConnectionRefusedError,
    ConnectionAbortedError,
    OSError,
)

gspread_retry = retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(5),
    retry=retry_all(
        retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        retry_if_not_exception_type(gspread.exceptions.WorksheetNotFound),
    ),
    reraise=True,
)

gspread_retry_fastfail = retry(
    wait=wait_exponential(multiplier=0.5, min=1, max=2),
    stop=stop_after_delay(10.0),
    retry=retry_all(
        retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        retry_if_not_exception_type(gspread.exceptions.WorksheetNotFound),
    ),
    reraise=True,
)


class SafeWorksheet:
    """Resilient wrapper for gspread.Worksheet operations."""

    def __init__(self, worksheet: gspread.Worksheet, retry_policy=None):
        self._worksheet = worksheet
        self._retry = retry_policy or gspread_retry

    @property
    def raw_worksheet(self) -> gspread.Worksheet:
        return self._worksheet

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._worksheet, name)
        if callable(attr):
            return self._retry(attr)
        return attr

    def get_all_records(self, *args, **kwargs):
        return self._retry(self._worksheet.get_all_records)(*args, **kwargs)

    def get_all_values(self, *args, **kwargs):
        return self._retry(self._worksheet.get_all_values)(*args, **kwargs)

    def row_values(self, *args, **kwargs):
        return self._retry(self._worksheet.row_values)(*args, **kwargs)

    def col_values(self, *args, **kwargs):
        return self._retry(self._worksheet.col_values)(*args, **kwargs)

    def cell(self, *args, **kwargs):
        return self._retry(self._worksheet.cell)(*args, **kwargs)

    def append_row(self, *args, **kwargs):
        return self._retry(self._worksheet.append_row)(*args, **kwargs)

    def append_rows(self, *args, **kwargs):
        return self._retry(self._worksheet.append_rows)(*args, **kwargs)

    def update(self, *args, **kwargs):
        return self._retry(self._worksheet.update)(*args, **kwargs)

    def update_cells(self, *args, **kwargs):
        return self._retry(self._worksheet.update_cells)(*args, **kwargs)

    def update_cell(self, *args, **kwargs):
        return self._retry(self._worksheet.update_cell)(*args, **kwargs)

    def clear(self, *args, **kwargs):
        return self._retry(self._worksheet.clear)(*args, **kwargs)

    def batch_update(self, *args, **kwargs):
        return self._retry(self._worksheet.batch_update)(*args, **kwargs)


class SafeSpreadsheet:
    """Resilient wrapper for gspread.Spreadsheet operations."""

    def __init__(self, spreadsheet: gspread.Spreadsheet, retry_policy=None):
        self._spreadsheet = spreadsheet
        self._retry = retry_policy or gspread_retry

    @property
    def raw_spreadsheet(self) -> gspread.Spreadsheet:
        return self._spreadsheet

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._spreadsheet, name)
        if callable(attr):
            return self._retry(attr)
        return attr

    def worksheet(self, title: str) -> SafeWorksheet:
        ws = self._retry(self._spreadsheet.worksheet)(title)
        return SafeWorksheet(ws, retry_policy=self._retry)

    def get_worksheet(self, index: int) -> SafeWorksheet:
        ws = self._retry(self._spreadsheet.get_worksheet)(index)
        return SafeWorksheet(ws, retry_policy=self._retry)

    def worksheets(self, *args, **kwargs) -> list[SafeWorksheet]:
        raw_list = self._retry(self._spreadsheet.worksheets)(*args, **kwargs)
        return [SafeWorksheet(ws, retry_policy=self._retry) for ws in raw_list]

    def add_worksheet(self, *args, **kwargs) -> SafeWorksheet:
        ws = self._retry(self._spreadsheet.add_worksheet)(*args, **kwargs)
        return SafeWorksheet(ws, retry_policy=self._retry)

    def batch_update(self, *args, **kwargs):
        return self._retry(self._spreadsheet.batch_update)(*args, **kwargs)


class SafeClient:
    """Resilient wrapper for gspread.Client operations."""

    def __init__(self, gc: gspread.Client, retry_policy=None):
        self._gc = gc
        self._retry = retry_policy or gspread_retry

    @property
    def raw_client(self) -> gspread.Client:
        return self._gc

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._gc, name)
        if callable(attr):
            return self._retry(attr)
        return attr

    def open(self, *args, **kwargs) -> SafeSpreadsheet:
        res = self._retry(self._gc.open)(*args, **kwargs)
        return SafeSpreadsheet(res, retry_policy=self._retry)

    def open_by_key(self, *args, **kwargs) -> SafeSpreadsheet:
        res = self._retry(self._gc.open_by_key)(*args, **kwargs)
        return SafeSpreadsheet(res, retry_policy=self._retry)

    def open_by_url(self, *args, **kwargs) -> SafeSpreadsheet:
        res = self._retry(self._gc.open_by_url)(*args, **kwargs)
        return SafeSpreadsheet(res, retry_policy=self._retry)

    def with_fast_fail(
        self, timeout: Tuple[float, float] = (3.0, 5.0), max_delay: float = 10.0
    ) -> SafeClient:
        """
        Returns a fast-fail view of this client with bounded socket timeout and Tenacity stop_after_delay.
        Guarantees threads unwind strictly before ThreadPool deadlines.
        """
        fast_retry = retry(
            wait=wait_exponential(multiplier=0.5, min=1, max=2),
            stop=stop_after_delay(max_delay),
            retry=retry_all(
                retry_if_exception_type(RETRYABLE_EXCEPTIONS),
                retry_if_not_exception_type(gspread.exceptions.WorksheetNotFound),
            ),
            reraise=True,
        )
        if hasattr(self._gc, "http_client") and hasattr(self._gc.http_client, "timeout"):
            self._gc.http_client.timeout = timeout
        return SafeClient(self._gc, retry_policy=fast_retry)


class IsolatedClientRegistry:
    """
    Client registry providing both completely unshared client factories (for zero cross-tenant
    state bleed) and thread-local cached clients with automatic fork safety.
    """

    def __init__(self, factory: Optional[Callable[[], Tuple[Any, ...]]] = None):
        self._factory = factory
        self._thread_local = threading.local()
        if hasattr(os, "register_at_fork"):
            os.register_at_fork(after_in_child=self.reset)

    def set_factory(self, factory: Callable[[], Tuple[Any, ...]]) -> None:
        self._factory = factory

    def get_isolated_clients(
        self, factory: Optional[Callable[[], Tuple[Any, ...]]] = None
    ) -> Tuple[Any, ...]:
        """Returns freshly instantiated unshared client instances bypassing all caches."""
        fn = factory or self._factory
        if not fn:
            raise RuntimeError("No client factory configured for IsolatedClientRegistry.")
        return fn()

    def get_thread_local_clients(
        self, factory: Optional[Callable[[], Tuple[Any, ...]]] = None
    ) -> Tuple[Any, ...]:
        """Returns cached clients per thread, preventing thread bleed while eliminating re-auth overhead."""
        if not hasattr(self._thread_local, "clients"):
            self._thread_local.clients = self.get_isolated_clients(factory=factory)
        return self._thread_local.clients

    def reset(self) -> None:
        """Clears cached clients in the current thread/process."""
        self._thread_local = threading.local()
