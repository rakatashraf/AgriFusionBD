"""
Stable error envelope for the FieldShift API (plan §2, report §9).

Every non-2xx response is shaped as::

    { "error": { "code": str, "message": str, "details": object|null } }

so the TanStack client can parse one shape regardless of the failure.
"""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("fieldshift.api")

# Map DRF/Django exceptions to a small, stable set of codes the UI knows.
_CODE_BY_STATUS = {
    400: "validation_error",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    415: "unsupported_media_type",
    429: "rate_limited",
    500: "internal_error",
}


def _envelope(code: str, message: str, details=None, http_status: int = 400):
    return Response(
        {"error": {"code": code, "message": message, "details": details}},
        status=http_status,
    )


def api_exception_handler(exc, context):
    """Wrap DRF's default handler into the stable envelope."""
    # Let DRF produce its canonical response (status + body) first.
    response = exception_handler(exc, context)

    if response is not None:
        code = _CODE_BY_STATUS.get(response.status_code, "error")
        # Pull a human message out of DRF's body when present.
        body = response.data
        message = "Request failed."
        details = body
        if isinstance(body, dict):
            if "detail" in body:
                message = str(body["detail"])
                details = body
            elif "error" in body and isinstance(body["error"], dict):
                # Already in our shape — pass through.
                return response
        return _envelope(code, message, details, response.status_code)

    # Unhandled exception — log and return a generic 500.
    logger.exception("Unhandled API exception: %s", exc)
    return _envelope("internal_error", "Something went wrong.", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
