import time
import pytest
from unittest.mock import MagicMock
import urllib3.exceptions
from requests.exceptions import ConnectionError as ReqConnectionError, ReadTimeout as ReqReadTimeout
import gspread.exceptions

from tenant_context_isolation_kit.clients import (
    SafeClient,
    SafeSpreadsheet,
    SafeWorksheet,
    IsolatedClientRegistry,
)


class TestGSpreadResilience:
    def test_safe_worksheet_retries_transient_read_timeout(self):
        mock_raw_ws = MagicMock()
        mock_pool = MagicMock()
        timeout_err = urllib3.exceptions.ReadTimeoutError(
            mock_pool, "https://sheets.googleapis.com", "Read timed out"
        )
        mock_raw_ws.row_values.side_effect = [timeout_err, ["Col1", "Col2"]]

        safe_ws = SafeWorksheet(mock_raw_ws)
        result = safe_ws.row_values(1)

        assert result == ["Col1", "Col2"]
        assert mock_raw_ws.row_values.call_count == 2

    def test_safe_worksheet_retries_protocol_error(self):
        mock_raw_ws = MagicMock()
        protocol_err = urllib3.exceptions.ProtocolError("Connection reset by peer")
        mock_raw_ws.update_cell.side_effect = [protocol_err, {"updated": True}]

        safe_ws = SafeWorksheet(mock_raw_ws)
        result = safe_ws.update_cell(1, 2, "Updated Value")

        assert result == {"updated": True}
        assert mock_raw_ws.update_cell.call_count == 2

    def test_safe_worksheet_does_not_retry_worksheet_not_found(self):
        mock_raw_ws = MagicMock()
        not_found_err = gspread.exceptions.WorksheetNotFound("Target worksheet missing")
        mock_raw_ws.get_all_values.side_effect = not_found_err

        safe_ws = SafeWorksheet(mock_raw_ws)
        with pytest.raises(gspread.exceptions.WorksheetNotFound):
            safe_ws.get_all_values()

        assert mock_raw_ws.get_all_values.call_count == 1

    def test_safe_spreadsheet_wraps_worksheets(self):
        mock_raw_sheet = MagicMock()
        raw_ws_1 = MagicMock()
        raw_ws_1.title = "Summary"
        mock_raw_sheet.worksheets.return_value = [raw_ws_1]

        safe_sheet = SafeSpreadsheet(mock_raw_sheet)
        worksheets = safe_sheet.worksheets()

        assert len(worksheets) == 1
        assert isinstance(worksheets[0], SafeWorksheet)
        assert worksheets[0].title == "Summary"

    def test_safe_client_open_by_key_returns_safe_spreadsheet(self):
        mock_gc = MagicMock()
        mock_raw_sheet = MagicMock()
        mock_gc.open_by_key.return_value = mock_raw_sheet

        safe_gc = SafeClient(mock_gc)
        sheet = safe_gc.open_by_key("sheet_999")

        assert isinstance(sheet, SafeSpreadsheet)
        assert sheet.raw_spreadsheet is mock_raw_sheet

    def test_safe_client_with_fast_fail_configures_timeout_and_retries(self):
        mock_gc = MagicMock(spec=gspread.Client)
        mock_gc.http_client = MagicMock()
        mock_gc.http_client.timeout = (10.0, 60.0)

        safe_gc = SafeClient(mock_gc)
        fast_gc = safe_gc.with_fast_fail(timeout=(2.0, 4.0), max_delay=5.0)

        assert mock_gc.http_client.timeout == (2.0, 4.0)
        assert isinstance(fast_gc, SafeClient)
        assert fast_gc.raw_client is mock_gc

    def test_safe_worksheet_fast_fail_aborts_quickly_on_repeated_errors(self):
        mock_raw_ws = MagicMock()
        mock_raw_ws.get_all_values.side_effect = TimeoutError("Simulated socket hang")

        mock_gc = MagicMock(spec=gspread.Client)
        mock_gc.http_client = MagicMock()
        safe_gc = SafeClient(mock_gc)
        fast_gc = safe_gc.with_fast_fail(timeout=(0.5, 1.0), max_delay=3.0)

        fast_ws = SafeWorksheet(mock_raw_ws, retry_policy=fast_gc._retry)

        t0 = time.time()
        with pytest.raises(TimeoutError):
            fast_ws.get_all_values()
        elapsed = time.time() - t0

        assert elapsed < 5.0


class TestIsolatedClientRegistry:
    def test_get_isolated_clients_always_instantiates_fresh(self):
        counter = {"calls": 0}

        def factory():
            counter["calls"] += 1
            return MagicMock(id=counter["calls"]), MagicMock(id=counter["calls"])

        registry = IsolatedClientRegistry(factory=factory)
        gc1, drive1 = registry.get_isolated_clients()
        gc2, drive2 = registry.get_isolated_clients()

        assert gc1 is not gc2
        assert drive1 is not drive2
        assert counter["calls"] == 2

    def test_get_thread_local_clients_caches_per_thread(self):
        counter = {"calls": 0}

        def factory():
            counter["calls"] += 1
            return MagicMock(id=counter["calls"]), MagicMock(id=counter["calls"])

        registry = IsolatedClientRegistry(factory=factory)
        gc1, drive1 = registry.get_thread_local_clients()
        gc2, drive2 = registry.get_thread_local_clients()

        assert gc1 is gc2
        assert drive1 is drive2
        assert counter["calls"] == 1

        # Reset process caches
        registry.reset()
        gc3, drive3 = registry.get_thread_local_clients()
        assert gc3 is not gc1
        assert counter["calls"] == 2
