"""Classify the original exception before its user-facing message is translated."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import errno
import math
import socket
import ssl

from yt_dlp.networking.exceptions import CertificateVerifyError, HTTPError, SSLError, TransportError

from .models import UserError


def _causes(error):
    pending, seen = [error], set()
    while pending:
        current = pending.pop()
        if not isinstance(current, BaseException) or id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        pending.extend([current.__cause__, current.__context__, getattr(current, "cause", None)])
        exc_info = getattr(current, "exc_info", None)
        if isinstance(exc_info, tuple) and len(exc_info) > 1:
            pending.append(exc_info[1])


def retry_after_seconds(value) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        try:
            date = parsedate_to_datetime(str(value))
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            seconds = (date - datetime.now(timezone.utc)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return None
    return max(0, seconds) if math.isfinite(seconds) else None


def failure_details(error: Exception, message: str) -> dict:
    result = {"message": message, "code": "unknown", "retryable": False}
    chain = list(_causes(error))
    if any(isinstance(item, UserError) for item in chain):
        return result | {"code": "user_action"}
    if any(isinstance(item, PermissionError) for item in chain):
        return result | {"code": "permission"}
    if any(isinstance(item, OSError) and (item.errno == errno.ENOSPC or getattr(item, "winerror", None) == 112)
           for item in chain):
        return result | {"code": "disk_full"}
    if any(isinstance(item, (CertificateVerifyError, SSLError, ssl.SSLError)) for item in chain):
        return result | {"code": "tls"}
    http = next((item for item in chain if isinstance(item, HTTPError)), None)
    if http is not None:
        status = http.status
        result.update(code=f"http_{status}", retryable=status in {408, 429} or 500 <= status <= 599)
        if status == 429:
            delay = retry_after_seconds(http.response.headers.get("Retry-After"))
            if delay is not None:
                result["retry_after_seconds"] = delay
        return result
    if any(isinstance(item, socket.gaierror) and item.errno != socket.EAI_AGAIN for item in chain):
        return result | {"code": "dns"}
    if any(isinstance(item, (TransportError, TimeoutError, ConnectionError))
           or isinstance(item, socket.gaierror) and item.errno == socket.EAI_AGAIN
           or isinstance(item, OSError) and item.errno in {errno.ETIMEDOUT, errno.ECONNRESET,
                                                           errno.ECONNABORTED, errno.ENETUNREACH,
                                                           errno.EHOSTUNREACH, errno.ECONNREFUSED}
           for item in chain):
        result.update(code="network", retryable=True)
    return result
