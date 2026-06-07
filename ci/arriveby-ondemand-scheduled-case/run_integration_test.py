#!/usr/bin/env python3
"""
Integration test for arrive-by scenario with historical, generator, and commuter.

All three scenario types (historical, generator, commuter) use arrive-by mode:
  - historical: each trip specifies ``arrv`` (target arrival time) instead of ``dept``
  - generator:  demands are generated with ``arrive_by: true``
  - commuter:   outbound/inbound legs use ``arrvOut``/``arrvIn`` instead of ``deptOut``/``deptIn``
"""

import json
import os
import random
import sys
import time
from dataclasses import dataclass
from typing import Any, Optional, List

import httpx

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

HTTP_TIMEOUT_DEFAULT = httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=5.0)
HTTP_TIMEOUT_SETUP = httpx.Timeout(connect=5.0, read=180.0, write=30.0, pool=5.0)
RETRY_ATTEMPTS = 6
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 8.0
SIMULATION_WAIT_TIMEOUT_SECONDS = 900
SIMULATION_POLL_INTERVAL_SECONDS = 1.0


@dataclass
class Trip:
    demand_id: str
    service: str
    dept: float
    org: str
    arrv: float
    dst: str

    def __str__(self) -> str:
        return (
            f"dept={self.dept} from {self.org} "
            f"via {self.service} -> arrv={self.arrv} "
            f"at {self.dst}"
        )


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


def upload_file(client: httpx.Client, url: str, filename: str) -> dict[str, Any]:
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
    return response.json()

def assert_message(data: dict[str, Any], expected_message: str) -> None:
    if data.get("message") == expected_message:
        print(f"  [OK] {data['message']}")
    else:
        print(f"  [FAIL] expected message={expected_message!r}, got: {data}")
        sys.exit(1)


def post(
    client: httpx.Client, url: str, params: Optional[dict] = None, **kwargs,
) -> dict[str, Any]:
    return request_with_retry(client, "POST", url, params=params, **kwargs).json()


def get_user_trips(
    events: list[dict[str, Any]], user_id: str
) -> list[Trip]:
    """Return only completed trips for the specified user."""

    departure: dict[str, Any] = {}
    trips: list[Trip] = []
    for event in events:
        details = event.get("details", {})
        if details.get("userId") != user_id:
            continue

        if event["eventType"] == "DEPARTED":
            departure = {
                "demand_id": details["demandId"],
                "service": event["source"],
                "dept": float(event["time"]),
                "org": details["location"]["locationId"],
            }
            continue

        if event["eventType"] == "ARRIVED":
            arrival: dict[str, Any] = {
                "demand_id": details["demandId"],
                "service": event["source"],
                "arrv": float(event["time"]),
                "dst": details["location"]["locationId"],
            }

            if departure["service"] != arrival["service"]:
                sys.exit(1)

            trips.append(
                Trip(
                    demand_id=departure["demand_id"],
                    service=departure["service"],
                    dept=departure["dept"],
                    org=departure["org"],
                    arrv=arrival["arrv"],
                    dst=arrival["dst"],
                )
            )

    return trips


def assert_arrived_by(trips: List[Trip], arrived: str, by: float) -> None:
    if not trips:
        print(f"  [FAIL] no trips found. expected arrival at {arrived} by {by}")
        sys.exit(1)

    last_trip = trips[-1]
    if last_trip.dst == arrived and last_trip.arrv <= by:
        print(f"  [OK] arrived at {arrived} by {by}: {last_trip}")
        return

    print(
        f"  [FAIL] expected final arrival at {arrived} by {by}, "
        f"got: {last_trip}. all trips: {trips}"
    )
    sys.exit(1)


def assert_used_service(trips: List[Trip], service: str) -> None:
    if any(trip.service == service for trip in trips):
        print(f"  [OK] service used: {service}")
        return

    print(f"  [FAIL] expected service {service} was not used. trips: {trips}")
    sys.exit(1)


def split_commuter_trips(
    trips: List[Trip], turnaround_dst: str
) -> tuple[List[Trip], List[Trip]]:
    """Split commuter trips into outbound and inbound segments.

    Outbound is from the first trip up to the first arrival at ``turnaround_dst``.
    Inbound is all trips after outbound.
    """
    if not trips:
        print("  [FAIL] commuter trips are empty")
        sys.exit(1)

    pivot_index = next((i for i, trip in enumerate(trips) if trip.dst == turnaround_dst), -1)
    if pivot_index < 0:
        print(f"  [FAIL] no turnaround destination found: {turnaround_dst}. trips: {trips}")
        sys.exit(1)

    outbound = trips[: pivot_index + 1]
    inbound = trips[pivot_index + 1 :]
    if not inbound:
        print(f"  [FAIL] inbound trips are missing after turnaround at {turnaround_dst}. trips: {trips}")
        sys.exit(1)

    return outbound, inbound


def main() -> None:
    with httpx.Client(timeout=HTTP_TIMEOUT_DEFAULT) as client:
        print("Waiting for required services to become reachable ...")
        wait_for_service_ready(client, "http://localhost:3000/openapi.json")
        wait_for_service_ready(client, "http://localhost:3001/openapi.json")
        wait_for_service_ready(client, "http://localhost:3010/openapi.json")

        # --- Setup simulators ---
        # scheduled
        response = upload_file(client, "http://localhost:3001/upload", "gtfs.zip")
        assert_message(response, "successfully uploaded. gtfs.zip")

        # --- Setup OpenTripPlanner ---
        response = upload_file(client, "http://localhost:3010/upload", "gtfs.zip")
        assert_message(response, "successfully uploaded. gtfs.zip")
        response = upload_file(client, "http://localhost:3010/upload", "otp-config.zip")
        assert_message(response, "successfully uploaded. otp-config.zip")

        # --- Setup broker ---
        with open(file_path("broker_setup.json"), "r", encoding="utf-8") as f:
            body = f.read()
        response = post(
            client,
            "http://localhost:3000/setup",
            headers={"Content-Type": "application/json"},
            content=body,
            timeout=HTTP_TIMEOUT_SETUP,
        )
        assert_message(response, "successfully configured.")

        # --- Lifecycle ---
        response = post(client, "http://localhost:3000/start")
        assert_message(response, "successfully started." )
        response = post(client, "http://localhost:3000/run", params={"until": 1440})
        assert_message(response, "successfully run.")

        print("Peeking simulation until running=False ...")
        deadline = time.time() + SIMULATION_WAIT_TIMEOUT_SECONDS

        while True:
            time.sleep(SIMULATION_POLL_INTERVAL_SECONDS)
            data = request_with_retry(client, "GET", "http://localhost:3000/peek").json()

            if data.get("running") is False:
                if data.get("success"):
                    print(f"  [OK] running=False with success=True: {data}")
                    break

                print(f"  [FAIL] expected success=True, got: {data}")
                sys.exit(1)
            
            if time.time() > deadline:
                print(
                    "  [FAIL] timed out waiting for simulation completion "
                    f"after {SIMULATION_WAIT_TIMEOUT_SECONDS} seconds"
                )
                sys.exit(1)
        
        response = post(client, "http://localhost:3000/finish")
        assert_message(response, "successfully finished.")

        # --- Retrieve results ---
        events = [json.loads(line) for line in request_with_retry(client, "GET", "http://localhost:3000/events").text.strip().splitlines()]

    # --- historical users: must complete a trip to toyama_court by 540 ---
    print("Checking U_1 trips ...")
    trips = get_user_trips(events, "U_1")
    assert_arrived_by(trips, "toyama_court", 570.0)
    assert_used_service(trips, "gtfs")

    # --- generator users: at least one GU_* user must complete a trip to toyama_court ---
    print("Checking GU_1 trips ...")
    trips = get_user_trips(events, "GU_1")
    assert_arrived_by(trips, "toyama_court", 570.0)
    assert_used_service(trips, "gtfs")

    # --- commuter CU_001: outbound to toyama_court by 555, inbound to toyama_station by 1095 ---
    print("Checking CU_1 trips ...")
    trips = get_user_trips(events, "CU_001")
    outbound_trips, inbound_trips = split_commuter_trips(trips, "toyama_court")
    assert_arrived_by(outbound_trips, "toyama_court", 555.0)
    assert_used_service(outbound_trips, "gtfs")
    assert_arrived_by(inbound_trips, "toyama_station", 1105.0)
    assert_used_service(inbound_trips, "gtfs")

    print("\nAll integration tests passed!")


if __name__ == "__main__":
    main()
