#!/usr/bin/env python3
"""
Integration test for the ondemand + oneway + generator + commuter scenario.

Run from the directory that contains this script (ci/ondemand-oneway-generator-commuter-case/):
    pip install -r requirements.txt
    python run_integration_test.py

The script expects docker compose to already be up and ready.
"""

import os
import random
import sys
import time
from typing import Optional

import httpx

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

HTTP_TIMEOUT_DEFAULT = httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=5.0)
RETRY_ATTEMPTS = 6
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 120.0
SIMULATION_WAIT_TIMEOUT_SECONDS = 900
SIMULATION_POLL_INTERVAL_SECONDS = 1.0


def file_path(filename: str) -> str:
    return os.path.join(SCRIPT_DIR, filename)


def request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    timeout: Optional[httpx.Timeout] = None,
    attempts: int = RETRY_ATTEMPTS,
    **kwargs,
) -> httpx.Response:
    for attempt in range(1, attempts + 1):
        try:
            response = client.request(method, url, timeout=timeout, **kwargs)
            if response.status_code in (429, 500, 502, 503, 504):
                raise httpx.HTTPStatusError(
                    f"retryable status code: {response.status_code}",
                    request=response.request,
                    response=response,
                )
            response.raise_for_status()
            return response
        except (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.RemoteProtocolError,
            httpx.HTTPStatusError,
        ) as exc:
            is_retryable = not isinstance(exc, httpx.HTTPStatusError) or (
                exc.response is not None
                and exc.response.status_code in (429, 500, 502, 503, 504)
            )
            if not is_retryable or attempt == attempts:
                raise

            backoff = min(
                INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1)), MAX_BACKOFF_SECONDS
            )
            backoff += random.uniform(0.0, 0.4)
            print(
                f"  [WARN] {method} {url} failed (attempt {attempt}/{attempts}): {exc}. "
                f"Retrying in {backoff:.1f}s ..."
            )
            time.sleep(backoff)

    raise RuntimeError("request retry loop ended unexpectedly")


def wait_for_service_ready(
    client: httpx.Client, url: str, timeout_seconds: int = 120
) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = client.get(
                url,
                timeout=httpx.Timeout(connect=2.0, read=5.0, write=5.0, pool=2.0),
            )
            # Accept any non-5xx status as a reachable service during startup.
            if response.status_code < 500:
                print(f"  [OK] Service is reachable: {url} ({response.status_code})")
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)

    print(f"  [FAIL] Timed out waiting for service: {url}")
    sys.exit(1)


def upload_file(client: httpx.Client, url: str, filename: str) -> None:
    filepath = file_path(filename)
    print(f"Uploading {filename} to {url} ...")
    with open(filepath, "rb") as f:
        payload = f.read()
    response = request_with_retry(
        client,
        "POST",
        url,
        files={"upload_file": (filename, payload, "application/octet-stream")},
    )
    data = response.json()
    expected = f"successfully uploaded. {filename}"
    if data.get("message") == expected:
        print(f"  [OK] {data['message']}")
    else:
        print(f"  [FAIL] unexpected response: {data}")
        sys.exit(1)


def post_json(
    client: httpx.Client, url: str, filename: str, expected_message: str
) -> None:
    filepath = file_path(filename)
    print(f"POST {url} with {filename} ...")
    with open(filepath, "r", encoding="utf-8") as f:
        body = f.read()
    response = request_with_retry(
        client,
        "POST",
        url,
        headers={"Content-Type": "application/json"},
        content=body,
    )
    data = response.json()
    if data.get("message") == expected_message:
        print(f"  [OK] {data['message']}")
    else:
        print(f"  [FAIL] unexpected response: {data}")
        sys.exit(1)


def post(
    client: httpx.Client, url: str, expected_message: str, params: Optional[dict] = None
) -> None:
    print(f"POST {url} ...")
    response = request_with_retry(client, "POST", url, params=params)
    data = response.json()
    if data.get("message") == expected_message:
        print(f"  [OK] {data['message']}")
    else:
        print(f"  [FAIL] unexpected response: {data}")
        sys.exit(1)


def get_and_check_json(
    client: httpx.Client, url: str, key: str, expected_value
) -> None:
    print(f"Polling {url} until running=False ...")
    deadline = time.time() + SIMULATION_WAIT_TIMEOUT_SECONDS

    while time.time() < deadline:
        response = request_with_retry(client, "GET", url)
        data = response.json()

        if data.get("running") is False:
            if data.get(key) == expected_value:
                print(f"  [OK] running=False and {key} = {expected_value}")
                return

            print(f"  [FAIL] expected {key}={expected_value}, got: {data}")
            sys.exit(1)

        time.sleep(SIMULATION_POLL_INTERVAL_SECONDS)

    print(
        "  [FAIL] timed out waiting for simulation completion "
        f"after {SIMULATION_WAIT_TIMEOUT_SECONDS} seconds"
    )
    sys.exit(1)


def get_and_check_line_count(client: httpx.Client, url: str, min_lines: int) -> None:
    print(f"GET {url} ...")
    response = request_with_retry(client, "GET", url)
    line_count = len(response.text.strip().splitlines())
    if line_count >= min_lines:
        print(f"  [OK] line count is {line_count} (>= {min_lines})")
    else:
        print(f"  [FAIL] line count is only {line_count} (expected >= {min_lines})")
        sys.exit(1)


def main() -> None:
    with httpx.Client(timeout=HTTP_TIMEOUT_DEFAULT) as client:
        print("Waiting for required services to become reachable ...")
        time.sleep(1)
        wait_for_service_ready(client, "http://localhost:3000/openapi.json")
        wait_for_service_ready(client, "http://localhost:3002/openapi.json")
        wait_for_service_ready(client, "http://localhost:3003/openapi.json")
        wait_for_service_ready(client, "http://localhost:3010/openapi.json")

        # --- Setup ondemand simulator and its planner ---
        upload_file(client, "http://localhost:3002/upload", "flex.zip")  # ondemand
        upload_file(
            client,
            "http://localhost:3010/upload",
            "flex.zip",
        )  # simple planner for ondemand

        # --- Setup oneway simulator and its planner ---
        upload_file(client, "http://localhost:3003/upload", "gbfs.zip")  # oneway
        upload_file(
            client,
            "http://localhost:3010/upload",
            "gbfs.zip",
        )  # simple planner for oneway

        # --- Setup broker ---
        post_json(
            client,
            "http://localhost:3000/setup",
            "broker_setup.json",
            "successfully configured.",
        )

        # --- Lifecycle ---
        post(client, "http://localhost:3000/start", "successfully started.")
        post(
            client,
            "http://localhost:3000/run",
            "successfully run.",
            params={"until": 2880},
        )

        get_and_check_json(client, "http://localhost:3000/peek", "success", True)
        post(client, "http://localhost:3000/finish", "successfully finished.")

        # --- Validate results ---
        get_and_check_line_count(client, "http://localhost:3000/events", min_lines=200)
        get_and_check_line_count(
            client, "http://localhost:3020/evaluation", min_lines=2
        )

    print("\nAll integration tests passed!")


if __name__ == "__main__":
    main()
