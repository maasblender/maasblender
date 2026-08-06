# Integration Tests

This directory contains the integration test cases.

## Directory Layout

```
ci/
├── README.md                              # This file
├── allowed-license.lst                    # Allowlist used by the license check workflow
├── ondemand-oneway-generator-commuter-case/   # Test case 1
└── scheduled-routedeviation-historical/       # Test case 2
```

## How It Works

Each test case is built around the following three files.

| File                      | Purpose                                                                                                     |
|---------------------------|-------------------------------------------------------------------------------------------------------------|
| `compose.yaml`            | Defines the Docker Compose stack required for the test, such as simulators, planners, and the broker.       |
| `requirements.txt`        | Lists the Python dependencies for the test script.                                                          |
| `run_integration_test.py` | The actual test runner. It calls the containers' HTTP APIs, runs the simulation, and validates the results. |

### Execution with GitHub Actions

`.github/workflows/integration.yaml` runs automatically on pushes and pull requests targeting the `main` branch.

```
┌──────────────┐         ┌──────────────────────────────────────────────────────┐
│  set-matrix  │──────▶  │  integration-test (matrix)                           │
│              │         │                                                      │
│ Automatically│         │  Runs each test case directory in parallel:          │
│ discovers    │         │    1. `docker compose up -d`                         │
│ test cases   │         │    2. `pip install -r requirements.txt`              │
│ under ci/    │         │    3. `python run_integration_test.py`               │
└──────────────┘         └──────────────────────────────────────────────────────┘
```

The `set-matrix` job dynamically discovers directories under `ci/` that contain `run_integration_test.py`, so you do not need to modify the workflow file when adding a new test case.

### Running a Test Locally

```bash
# Move to a test case directory
cd ci/ondemand-oneway-generator-commuter-case

# Start the containers
docker compose up -d

# Install Python dependencies
pip install -r requirements.txt

# Run the integration test
python run_integration_test.py
```
