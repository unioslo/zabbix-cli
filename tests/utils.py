from __future__ import annotations

import json
from typing import Any
from typing import Optional

from pytest_httpserver import HTTPServer
from werkzeug import Request
from werkzeug import Response
from zabbix_cli.pyzabbix.types import Json


def add_zabbix_endpoint(
    httpserver: HTTPServer,
    method: str,  # method is zabbix API method, not HTTP method
    *,
    params: dict[str, Any],
    response: Json,
    auth: Optional[str] = None,
    headers: Optional[dict[str, str]] = None,
    id: int = 0,
    check_id: bool = False,
) -> None:
    """Add an endpoint mocking a Zabbix API endpoint."""

    # Use a custom handler to check request contents
    def handler(request: Request) -> Response:
        # Get the JSON body of the request
        # Request has content type 'application/json-rpc'
        # so request.json() method does not work
        request_json = json.loads(request.data.decode())

        # Zabbix API method
        assert request_json["method"] == method

        # Only check the params we passed are correct
        # Missing/extra params are not checked
        for k, v in params.items():
            assert k in request_json["params"]
            assert request_json["params"][k] == v

        # Test auth token in body (< 6.4.0)
        if auth:
            assert request_json["auth"] == auth

        # Test headers
        if headers:
            for k, v in headers.items():
                assert request.headers[k] == v

        # Only check ID if we are told to
        # In parametrized tests, it can be difficult to determine the ID
        # depending on auth method, server version, etc.
        if check_id:
            assert request_json["id"] == id

        resp_json = json.dumps({"jsonrpc": "2.0", "result": response, "id": id})
        return Response(resp_json, status=200, content_type="application/json")

    httpserver.expect_oneshot_request(
        "/api_jsonrpc.php",
        method="POST",
    ).respond_with_handler(handler)


def add_zabbix_version_endpoint(
    httpserver: HTTPServer, version: str, id: int = 0
) -> None:
    """Add an endpoint emulating the Zabbix apiiinfo.version method."""
    add_zabbix_endpoint(
        httpserver,
        method="apiinfo.version",
        params={},
        response=version,
        id=id,
    )
