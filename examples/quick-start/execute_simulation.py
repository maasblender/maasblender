import json
import sys
import time
import zipfile
from pathlib import Path
from datetime import datetime
import httpx
import csv
import io


def extract_gtfs_period(zip_path: Path) -> tuple[datetime, datetime]:
    """
    Extract the overall validity period of a GTFS feed.
    This function reads `calendar.txt` inside the GTFS zip file and
    calculates `start_date` and `end_date` across all services.

    Args:
        zip_path (Path): Path to the GTFS zip file.

    Return value:
        Tuple (datetime, datetime)

    Raises:
        GTFSPeriodException:
            If `calendar.txt` is missing or valid start/end dates cannot be determined.
    """

    with zipfile.ZipFile(zip_path, "r") as z:
        # Derive validity period from calendar.txt
        if "calendar.txt" not in z.namelist():
            raise GTFSPeriodException("calendar.txt not found")

        with z.open("calendar.txt") as f:
            text_stream = io.TextIOWrapper(f, encoding="utf-8")
            reader = csv.DictReader(text_stream)

            start_dates = []
            end_dates = []

            for row in reader:
                if row.get("start_date") and row.get("end_date"):
                    start_dates.append(datetime.strptime(row["start_date"], "%Y%m%d"))
                    end_dates.append(datetime.strptime(row["end_date"], "%Y%m%d"))
            if start_dates and end_dates:
                return min(start_dates), max(end_dates)
            else:
                raise GTFSPeriodException(
                    "calendar.txt does not contain valid start/end dates"
                )


def validate_reference_times(settings_path: Path):
    """
    Load broker_setup.json and verify that the reference_time for each GTFS service falls within the GTFS feed's validity period.
    This is a soft validation:
        - Logs warnings instead of throwing exceptions.
        - Out-of-range dates may be intentional depending on scenario design.
    Networks explicitly defined as type="gtfs" are targeted.
    """
    print_section("GTFS Validity Check")

    with open(settings_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Extract network definitions under planner.details
    planner = config.get("planner", {})
    networks = planner.get("details", {}).get("networks", {})
    for network_name, network in networks.items():
        if network.get("type") != "gtfs":
            continue
        service = config.get(network_name)
        # Skip when no service definition exists.
        if not service:
            continue

        details = service.get("details", {})
        reference_time = details.get("reference_time")
        input_files = details.get("input_files", [])

        if not reference_time:
            continue

        reference_date = datetime.strptime(reference_time, "%Y%m%d")

        for file_info in input_files:
            filename = file_info["filename"]
            zip_path = Path(filename)

            try:
                start_date, end_date = extract_gtfs_period(zip_path)
                if start_date and end_date:
                    if reference_date < start_date or reference_date > end_date:
                        print(
                            f"[⚠ WARN] reference_time={reference_time} "
                            f"is outside GTFS valid period "
                            f"({start_date.date()} - {end_date.date()}) "
                            f"for service '{network_name}'."
                        )
                    else:
                        print(
                            f"[✅ OK] reference_time={reference_time} "
                            f"is within GTFS valid period "
                            f"({start_date.date()} - {end_date.date()}) "
                            f"for service '{network_name}'."
                        )
            except GTFSPeriodException as e:
                print(
                    f"[❌ ERROR] Could not determine GTFS valid period "
                    f"for service '{network_name}'\n:{e}"
                )
                continue


def print_section(message: str):
    """Function to print a console section header."""
    line = "=" * 60
    print(f"\n{line}")
    print(message)
    print(line)


def main():
    otp_config = Path("otp-config.zip")
    gtfs = Path("gtfs.zip")
    settings = Path("broker_setup.json")

    # GTFS Validity Check
    validate_reference_times(settings)

    with httpx.Client() as client:
        # 1. Uploads configuration files to the otp planner service
        with open(otp_config, "rb") as otp_config_file:
            response = client.post(
                "http://localhost:3010/upload",
                files={
                    "upload_file": (
                        "otp-config.zip",
                        otp_config_file,
                        "application/x-zip-compressed",
                    )
                },
                headers={"accept": "application/json"},
            )
            if response.status_code != 200:
                print(response.text)
                return
            print(response.json())

        with open(gtfs, "rb") as gtfs_file:
            response = client.post(
                "http://localhost:3010/upload",
                files={
                    "upload_file": (
                        "gtfs.zip",
                        gtfs_file,
                        "application/x-zip-compressed",
                    )
                },
                headers={"accept": "application/json"},
            )
            if response.status_code != 200:
                print(response.text)
                return
            print(response.json())

        # 2. Uploads GTFS files to the scheduled simulation service
        with open(gtfs, "rb") as gtfs_file2:
            response = client.post(
                "http://localhost:3001/upload",
                files={
                    "upload_file": (
                        "gtfs.zip",
                        gtfs_file2,
                        "application/x-zip-compressed",
                    )
                },
                headers={"accept": "application/json"},
            )
            if response.status_code != 200:
                print(response.text)
                return
            print(response.json())

        # 3. Sets up the broker service with the configuration file
        # Sends a request to `localhost:3000/setup` to configure all services.
        # This step may take a long time and could potentially time out.
        with open(settings, "r", encoding="utf-8") as file:
            data = json.load(file)
        response = client.post(
            "http://localhost:3000/setup",
            json=data,
            headers={"accept": "application/json", "Content-Type": "application/json"},
            timeout=720,
        )
        try:
            print(response.json())
            if response.status_code != 200:
                return
        except json.JSONDecodeError:
            print(response.text)
            sys.exit(-1)

        # 4. Starts the broker service
        # Sends a request to `localhost:3000/start` to start the initialization process.
        response = client.post(
            "http://localhost:3000/start", headers={"accept": "application/json"}
        )
        try:
            print(response.json())
        except json.JSONDecodeError:
            print(response.text)
            sys.exit(-1)

        # 5. Runs the simulation
        # Sends a request to `localhost:3000/run` with a simulation duration parameter (`until=1440`).
        response = client.post(
            "http://localhost:3000/run",
            params={"until": "1440"},
            headers={"accept": "application/json"},
        )
        try:
            print(response.json())
        except json.JSONDecodeError:
            print(response.text)
            sys.exit(-2)

        # 6. Periodically checks the simulation status
        # Polls the broker service every 10 seconds to check if the simulation is still running.
        running = True
        while running:
            time.sleep(10)
            response = client.get(
                "http://localhost:3000/peek", headers={"accept": "application/json"}
            )
            try:
                peek = response.json()
                running = peek["running"]
                next_time = peek["next"]
                if peek["success"]:
                    print("running:", next_time)
                else:
                    print("failed", next_time)
                    sys.exit(-3)
            except json.JSONDecodeError:
                print(response.text)
        print("successfully finished.")

        # 7. Retrieves simulation results after simulation completion
        # Fetches event logs from `localhost:3000/events` and saves them to `output/events.txt`.
        response = client.get("http://localhost:3000/events")
        with open("events.txt", "w", encoding="utf-8") as file:
            file.write(response.text)
        print("All events recorded to events.txt")


if __name__ == "__main__":
    main()
