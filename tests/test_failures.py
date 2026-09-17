from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import errno

import pytest
from yt_dlp.networking.common import Response
from yt_dlp.networking.exceptions import CertificateVerifyError, HTTPError, TransportError
from yt_dlp.utils import DownloadError, ExtractorError

from vidveya.failures import failure_details, retry_after_seconds
from vidveya.models import UserError


@pytest.mark.parametrize("status,retryable", [(408, True), (429, True), (500, True), (503, True),
                                             (401, False), (403, False), (404, False)])
def test_nested_http_failures(status, retryable):
    import io
    cause = HTTPError(Response(io.BytesIO(), "https://example.invalid", {"Retry-After": "120"}, status))
    wrapped = ExtractorError("failure", cause=cause)
    error = DownloadError("failure", exc_info=(type(wrapped), wrapped, None))
    result = failure_details(error, "safe message")
    assert result["retryable"] is retryable and result["code"] == f"http_{status}"
    assert result["message"] == "safe message"
    if status == 429:
        assert result["retry_after_seconds"] == 120


@pytest.mark.parametrize("error,retryable", [(TimeoutError(), True), (ConnectionResetError(), True),
                                             (TransportError("lost"), True), (UserError("missing audio"), False),
                                             (PermissionError(), False), (OSError(errno.ENOSPC, "full"), False),
                                             (CertificateVerifyError("certificate"), False), (RuntimeError(), False)])
def test_only_temporary_failures_retry(error, retryable):
    assert failure_details(error, "safe")["retryable"] is retryable


def test_retry_after_accepts_http_date_and_rejects_nonfinite_values():
    date = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=300))
    assert 298 < retry_after_seconds(date) <= 300
    for invalid in ("bad", "inf", "nan", None):
        assert retry_after_seconds(invalid) is None
