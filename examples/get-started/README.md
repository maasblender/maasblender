# Get Started Examples

Simple code to get started with maasblender.
This example simulates a multimodal MaaS environment combining scheduled and on-demand mobility services:

- Scheduled Mobility Service: Uses GTFS to simulate fixed-route public transportation, such as buses following predefined schedules.
- On-Demand Mobility Service: Uses GTFS-Flex to simulate flexible, demand-responsive transit, such as on-demand shuttle buses.

These two mobility models run together within the simulation, demonstrating their interoperability within the MaaS ecosystem.

## Files

- `otp-config.zip`: OpenTripPlanner configuration file.
- `gtfs.zip`: General Transit Feed Specification data.
- `gtfs_flex.zip`: Flexible GTFS data.
- `broker.json`: MaaSBlender configuration file.
- `compose.yml`: Defines the required containers and services.
- `execution.py`: A Python script to execute the simulation by configuration necessary files and interacting with different components of MaaSBlender.

## Prerequisites

Ensure you have the following installed:
- Docker and Docker Compose
- Python 3.x
  - Required Python packages (install with `pip install httpx`)

## Running the Simulation

1. Start the necessary containers using Docker Compose:

   ```sh
   cd examples/get-started
   docker compose up -d
   ```

2. Execute the simulation script:

   ```sh
   cd examples/get-started
   python execution.py
   ```
