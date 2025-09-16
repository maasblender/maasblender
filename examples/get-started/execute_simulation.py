import json
import time
from pathlib import Path

import httpx


def main():
    otp_config = Path("jobui/otp-config.zip")
    gtfs = Path("jobui/2023_diagram/gtfs.zip")
    gtfs_flex = Path("jobui/gtfs_flex_mod.zip")
    settings = Path("data/broker_setup_graphql.json")

    with httpx.Client() as client:
        # 1. Uploads configuration files to the otp planner service
        response = client.post(
            "http://localhost:3010/upload",
            files={
                "upload_file": (
                    "otp-config.zip",
                    open(otp_config, "rb"),
                    "application/x-zip-compressed",
                )
            },
            headers={"accept": "application/json"},
        )
        if not response.status_code == 200:
            print(response.text)
            return
        print(response.json())

        response = client.post(
            "http://localhost:3010/upload",
            files={
                "upload_file": (
                    "gtfs.zip",
                    open(gtfs, "rb"),
                    "application/x-zip-compressed",
                )
            },
            headers={"accept": "application/json"},
        )
        if not response.status_code == 200:
            print(response.text)
            return
        print(response.json())

        response = client.post(
            "http://localhost:3010/upload",
            files={
                "upload_file": (
                    "gtfs_flex.zip",
                    open(gtfs_flex, "rb"),
                    "application/x-zip-compressed",
                )
            },
            headers={"accept": "application/json"},
        )
        if not response.status_code == 200:
            print(response.text)
            return
        print(response.json())

        # 2. Uploads GTFS files to the scheduled simulation service
        response = client.post(
            "http://localhost:3001/upload",
            files={
                "upload_file": (
                    "gtfs.zip",
                    open(gtfs, "rb"),
                    "application/x-zip-compressed",
                )
            },
            headers={"accept": "application/json"},
        )
        if not response.status_code == 200:
            print(response.text)
            return
        print(response.json())

        # 3. Uploads GTFS-FLEX files to the ondemand simulation service
        response = client.post(
            "http://localhost:3002/upload",
            files={
                "upload_file": (
                    "gtfs_flex.zip",
                    open(gtfs_flex, "rb"),
                    "application/x-zip-compressed",
                )
            },
            headers={"accept": "application/json"},
        )
        if not response.status_code == 200:
            print(response.text)
            return
        print(response.json())

        # 4. Sets up the broker service with the configuration file
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
        except Exception:
            print(response.text)
            exit(-1)

        # 5. Starts the broker service
        # Sends a request to `localhost:3000/start` to start the initialization process.
        response = client.post(
            "http://localhost:3000/start", headers={"accept": "application/json"}
        )
        try:
            print(response.json())
        except Exception:
            print(response.text)
            exit(-1)

        # 6. Runs the simulation
        # Sends a request to `localhost:3000/run` with a simulation duration parameter (`until=4320`).
        response = client.post(
            "http://localhost:3000/run",
            params={"until": "4320"},
            headers={"accept": "application/json"},
        )
        try:
            print(response.json())
        except Exception:
            print(response.text)
            exit(-2)

        # 7. Periodically checks the simulation status
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
                    exit(-3)
            except Exception:
                print(response.text)

        # 8. Retrieves simulation results after simulation completion
        # Fetches event logs from `localhost:3000/events` and saves them to `output/events.txt`.
        response = client.get("http://localhost:3000/events")
        with open("output/events.txt", "w", encoding="utf-8") as file:
            file.write(response.text)


if __name__ == "__main__":
    main()
