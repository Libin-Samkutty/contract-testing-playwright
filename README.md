# Contract Testing with Playwright

A contract testing system that validates live API responses against versioned OpenAPI/JSON Schema contracts, detects breaking changes between schema versions, and integrates into CI/CD pipelines to prevent API regressions.

---

## Table of Contents

- [What is Contract Testing?](#what-is-contract-testing)
- [How This Project Works](#how-this-project-works)
- [Target APIs](#target-apis)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running Tests](#running-tests)
- [Using the Scripts](#using-the-scripts)
- [Adding a New API](#adding-a-new-api)
- [Understanding the Diff Engine](#understanding-the-diff-engine)
- [CI/CD Pipeline](#cicd-pipeline)
- [Glossary](#glossary)

---

## What is Contract Testing?

When you build software that calls an external API, you rely on that API to behave consistently — to return the fields you expect, in the formats you expect. **Contract testing** is how you verify that promise is kept.

A **contract** is a formal description of what an API endpoint should return — which fields exist, what types they are, which are required, and what values are allowed. This project stores those contracts as [OpenAPI](https://swagger.io/specification/) YAML files.

### Why not just write regular tests?

Regular integration tests check that your code works *right now*, but they don't tell you *why* it breaks when an API changes. Contract tests give you:

- **Early warning** — catch breaking API changes before they reach production.
- **A shared language** — the contract file is readable by humans and machines alike.
- **Version history** — you can compare two versions of a contract and see exactly what changed.

### Breaking vs. Non-Breaking Changes

Not every API change is dangerous. This project classifies changes into two categories:

| Change | Classification | Why |
|---|---|---|
| Field removed from response | **Breaking** | Your code that reads that field will fail |
| Field type changed (e.g. `int` → `string`) | **Breaking** | Parsing will fail |
| Endpoint removed | **Breaking** | Direct 404 errors |
| Enum value removed | **Breaking** | Your code may not handle the missing value |
| New optional field added to response | Non-breaking | Old clients can safely ignore it |
| New endpoint added | Non-breaking | Old clients never call it |
| Description or documentation changed | Non-breaking | No runtime impact |
| Required request field made optional | Non-breaking | Server becomes more permissive |

---

## How This Project Works

The system has five main components:

```
Live API  →  Playwright (HTTP)  →  ValidationEngine  →  Contracts (YAML)
                                         ↑
                                    DiffEngine
                                    (v1.0 vs v1.1)
```

1. **Contract Storage** — OpenAPI specs in `/contracts/{api}/{version}.yaml` act as the source of truth.
2. **Validation Engine** — `src/validation_engine.py` fetches live API responses via Playwright and validates them against the stored contract.
3. **Diff Engine** — `src/diff_engine.py` compares two contract versions and flags breaking changes.
4. **Coverage Reporting** — tracks which endpoints were exercised by the test suite.
5. **CI/CD** — GitHub Actions runs all of the above automatically on every PR and push.

---

## Target APIs

These are the four public, free APIs used for testing. No authentication is required.

| API | Base URL | What it models |
|---|---|---|
| Swagger Petstore (v3) | `https://petstore3.swagger.io/api/v3` | A pet store — classic CRUD example |
| RealWorld (Conduit) | `https://api.realworld.io/api` | A blogging platform |
| JSONPlaceholder | `https://jsonplaceholder.typicode.com` | Fake REST API for prototyping |
| OpenBreweryDB | `https://api.openbrewerydb.org/v1` | Database of breweries |

---

## Project Structure

```
contract-testing-playwright/
├── .github/
│   └── workflows/
│       └── contract-tests.yml      # CI/CD pipeline (5 jobs)
│
├── contracts/                      # Versioned OpenAPI specs (source of truth)
│   ├── jsonplaceholder/
│   │   ├── v1.0.0.yaml
│   │   └── v1.1.0.yaml
│   ├── openbrewerydb/
│   │   ├── v1.0.0.yaml
│   │   └── v1.1.0.yaml
│   ├── petstore/
│   │   ├── v1.0.0.yaml
│   │   ├── v1.1.0.yaml
│   │   └── v2.0.0.yaml
│   └── realworld/
│       ├── v1.0.0.yaml
│       └── v1.1.0.yaml
│
├── src/                            # Core library modules
│   ├── adapters.py                 # HTTP response adapters
│   ├── contract_manager.py         # Load, resolve, and version contracts
│   ├── diff_engine.py              # Breaking change detection
│   ├── schema_generator.py         # Auto-generate schemas from live responses
│   └── validation_engine.py        # Validate responses against contracts
│
├── scripts/                        # Runnable CLI tools
│   ├── coverage_report.py          # Endpoint coverage analysis
│   ├── diff_contracts.py           # Compare two contract versions
│   ├── generate_schema.py          # Auto-generate a schema from a live API
│   └── validate_specs.py           # Validate spec files against the OAS meta-schema
│
├── tests/
│   ├── conftest.py                 # Shared fixtures, helpers, and Playwright setup
│   ├── test_diff_engine.py         # Unit tests for the diff engine
│   ├── test_jsonplaceholder.py     # Contract tests — JSONPlaceholder
│   ├── test_openbrewerydb.py       # Contract tests — OpenBreweryDB
│   ├── test_petstore.py            # Contract tests — Swagger Petstore
│   └── test_realworld.py           # Contract tests — RealWorld
│
├── pyproject.toml                  # Project metadata and pytest configuration
├── requirements.txt                # Pinned dependencies
└── README.md
```

---

## Prerequisites

- **Python 3.10 or later** — [Download here](https://www.python.org/downloads/)
- **pip** — comes bundled with Python
- An internet connection (tests call live external APIs)

To check your Python version:

```bash
python --version
```

---

## Installation

### 1. Clone the repository

```bash
git clone <repo-url>
cd contract-testing-playwright
```

### 2. Create a virtual environment

A virtual environment keeps project dependencies isolated from your system Python.

```bash
# Create the environment
python -m venv venv

# Activate it
# On macOS / Linux:
source venv/bin/activate

# On Windows (Command Prompt):
venv\Scripts\activate.bat

# On Windows (PowerShell):
venv\Scripts\Activate.ps1
```

You'll see `(venv)` appear in your terminal prompt when it's active.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright browsers

Playwright needs a browser binary to make HTTP requests. We only need Chromium.

```bash
playwright install chromium
```

### 5. Verify the setup

```bash
pytest --collect-only
```

This should list all available tests without running them. If you see errors, check that the virtual environment is active and dependencies are installed.

---

## Running Tests

### Run all contract tests

```bash
pytest tests/ -v
```

### Run tests for a single API

```bash
pytest tests/test_petstore.py -v
pytest tests/test_realworld.py -v
pytest tests/test_jsonplaceholder.py -v
pytest tests/test_openbrewerydb.py -v
```

### Run diff engine unit tests only (no network required)

```bash
pytest tests/test_diff_engine.py -v
```

### Run tests by marker

The project defines custom pytest markers:

```bash
# Only tests that call live external APIs
pytest -m live_api -v

# Only diff / breaking-change tests
pytest -m diff -v
```

### Understanding test output

A passing run looks like:

```
tests/test_petstore.py::TestGetPetById::test_get_pet_returns_correct_schema PASSED
tests/test_petstore.py::TestGetPetById::test_get_pet_not_found PASSED
```

A failing contract test will show exactly which field or type was wrong:

```
FAILED tests/test_petstore.py::TestCreatePet::test_create_pet_response_schema
AssertionError: Pet creation response validation failed:
  ["Field 'id' expected int, got str"]
```

---

## Using the Scripts

These are standalone CLI tools you can run directly.

### Validate all spec files

Checks every contract YAML against the official OpenAPI 3.0 meta-schema.

```bash
python scripts/validate_specs.py
```

To validate a single file:

```bash
python scripts/validate_specs.py --spec contracts/petstore/v1.0.0.yaml
```

### Compare two contract versions

The diff tool compares two OpenAPI files and reports which changes are breaking and which are safe.

```bash
python scripts/diff_contracts.py --previous contracts/petstore/v1.0.0.yaml --current contracts/petstore/v2.0.0.yaml
```

Example output (petstore v2.0.0 contains intentional breaking changes):

```
======================================================================
CONTRACT DIFF REPORT
Previous: contracts/petstore/v1.0.0.yaml
Current:  contracts/petstore/v2.0.0.yaml
======================================================================

Compatibility Score: X 65/100
Breaking Changes:     2
Non-Breaking Changes: 5

BREAKING CHANGES:
--------------------------------------------------
  [endpoint_removed] -20pts  root['paths']['/pet/findByStatus']
  [type_changed]     -15pts  root['components']['schemas']['Pet']['properties']['id']['type']

NON-BREAKING CHANGES:
--------------------------------------------------
  [dictionary_item_added] root['paths']['/pet/findByTags']
  [dictionary_item_added] root['components']['schemas']['Pet']['properties']['updatedAt']
  [values_changed] root['components']['schemas']['Pet']['properties']['id']['format']

RESULT: BREAKING CHANGES DETECTED — deployment blocked
======================================================================
```

To compare a non-breaking upgrade (score 100):

```bash
python scripts/diff_contracts.py --previous contracts/openbrewerydb/v1.0.0.yaml --current contracts/openbrewerydb/v1.1.0.yaml
```

To save the report to a JSON file:

```bash
python scripts/diff_contracts.py --previous contracts/openbrewerydb/v1.0.0.yaml --current contracts/openbrewerydb/v1.1.0.yaml --output reports/diff-report.json
```

To make the script exit with a non-zero code if breaking changes are found (useful in CI):

```bash
python scripts/diff_contracts.py --previous contracts/openbrewerydb/v1.0.0.yaml --current contracts/openbrewerydb/v1.1.0.yaml --fail-on-breaking
```

### Auto-generate a contract from a live API

If an API doesn't have an OpenAPI spec, you can generate one by sampling a live endpoint. The tool calls the URL, infers a JSON Schema from the response, and wraps it in an OpenAPI 3.0 document.

```bash
python scripts/generate_schema.py --url https://jsonplaceholder.typicode.com/posts --output contracts/jsonplaceholder/v1.0.0.yaml --title "JSONPlaceholder Posts API"
```

> The generated schema is a starting point. Review it manually and tighten the types as needed before committing.

### Generate a coverage report

Shows which endpoints defined in a spec were actually tested.

```bash
python scripts/coverage_report.py --spec contracts/openbrewerydb/v1.1.0.yaml --auto-discover
```

After running the test suite, a `coverage_data.json` file is produced. Pass it to the coverage script for a more accurate report:

```bash
python scripts/coverage_report.py --spec contracts/openbrewerydb/v1.1.0.yaml --coverage coverage_data.json --output reports/coverage-report.json
```

---

## Adding a New API

Follow these steps to add contract tests for a new API.

### Step 1 — Create the contract directory

```bash
mkdir contracts/my-api
```

### Step 2 — Add the OpenAPI spec

If the API publishes its own spec, download it:

```bash
curl -o contracts/my-api/v1.0.0.yaml https://api.example.com/openapi.yaml
```

If not, generate one from a live endpoint:

```bash
python scripts/generate_schema.py --url https://api.example.com/users --output contracts/my-api/v1.0.0.yaml --title "My API"
```

### Step 3 — Validate the spec

```bash
python scripts/validate_specs.py --spec contracts/my-api/v1.0.0.yaml
```

Fix any reported errors before continuing.

### Step 4 — Create the test file

Create `tests/test_my_api.py`. Use an existing test file as a reference (e.g. [tests/test_petstore.py](tests/test_petstore.py)).

```python
import pytest
from conftest import record_coverage, validate_object_schema

ITEM_REQUIRED_FIELDS = {
    "id": int,
    "name": str,
}

class TestGetItems:
    def test_list_returns_array(self, api_context):
        response = api_context.get("https://api.example.com/items")
        assert response.status == 200
        record_coverage("GET", "/items", response.status)
        assert isinstance(response.json(), list)

    def test_item_schema(self, api_context):
        response = api_context.get("https://api.example.com/items/1")
        assert response.status == 200
        errors = validate_object_schema(response.json(), ITEM_REQUIRED_FIELDS)
        assert not errors, errors
```

### Step 5 — Add a URL fixture to conftest.py (optional)

If you want a named fixture for the base URL, add it to `tests/conftest.py`:

```python
@pytest.fixture(scope="session")
def my_api_url():
    return "https://api.example.com"
```

### Step 6 — Tag the initial version

```bash
git add contracts/my-api/v1.0.0.yaml tests/test_my_api.py
git commit -m "Add contract tests for My API v1.0.0"
git tag -a v1.0.0 -m "Initial contract for My API"
git push origin v1.0.0
```

---

## Understanding the Diff Engine

The diff engine (`src/diff_engine.py`) uses [DeepDiff](https://github.com/seperman/deepdiff) to compare two OpenAPI spec dictionaries and classifies every structural change.

### Compatibility Score

Each diff produces a score from **0 to 100**, calculated by subtracting a severity-weighted penalty for each breaking change:

| Breaking change type | Penalty |
|---|---|
| Endpoint removed | −20 |
| Type changed | −15 |
| Required field changed | −10 |
| Other breaking change | −10 |

Score = `max(0, 100 − sum of penalties)`

| Score | Meaning |
|---|---|
| **100** | Fully backward-compatible — no breaking changes |
| **70–99** | Minor breakage — warning, investigate before deploying |
| **40–69** | Significant breakage — likely needs a major version bump |
| **< 40** | Severe breakage — pipeline will fail |

### When does the pipeline fail?

The `should_fail_pipeline` property returns `True` when **3 or more** breaking changes are detected. This threshold avoids false positives from minor spec drift while still blocking genuinely dangerous releases.

### Classification rules

| DeepDiff event | Path context | Classification |
|---|---|---|
| Item removed | `paths → {path}` | **Breaking** — endpoint removed |
| Item removed | `responses → ...` | **Breaking** — response field removed |
| Item removed | `requestBody → ...` | Non-breaking — server becomes more permissive |
| Item added | `paths → {path}` | Non-breaking — new endpoint |
| Item added | `requestBody → required` | **Breaking** — new required request field |
| Type changed | anywhere | **Breaking** |
| Enum value removed | `enum` | **Breaking** |
| Required entry removed | `responses → required` | Non-breaking — field made optional |

---

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/contract-tests.yml`) runs automatically on:

- Every **pull request** to `main` or `master`
- Every **push** to `main` or `master`
- Every **version tag push** (`v*.*.*`)
- Manually via **workflow_dispatch**

### Jobs

```
validate-specs
      │
      ├──▶ contract-tests ──▶ coverage-report
      │
(on tag push only)
diff-check
```

| Job | What it does | Fails pipeline? |
|---|---|---|
| `validate-specs` | Validates all YAML files against the OAS meta-schema | Yes |
| `contract-tests` | Runs all contract tests | Yes |
| `diff-check` | Runs contract diff on version tag pushes | Yes (if breaking changes) |
| `coverage-report` | Generates endpoint coverage summary | No |

All test results and coverage data are uploaded as GitHub Actions artifacts after each run.

---

## Glossary

| Term | Definition |
|---|---|
| **Contract** | A formal specification (OpenAPI YAML) describing the expected shape of an API's requests and responses |
| **OpenAPI** | A standard format (formerly Swagger) for describing REST APIs in YAML or JSON |
| **JSON Schema** | A vocabulary for describing and validating the structure of JSON data |
| **Breaking change** | An API change that will cause existing clients to fail (e.g. removing a field) |
| **Non-breaking change** | An API change that is backward-compatible (e.g. adding a new optional field) |
| **Playwright** | A browser automation library; used here for its API request context to make HTTP calls |
| **SemVer** | Semantic Versioning — a versioning scheme (`MAJOR.MINOR.PATCH`) that communicates the nature of changes |
| **$ref** | An OpenAPI/JSON Schema reference that points to a reusable schema component |
| **prance** | A Python library that resolves `$ref` references in OpenAPI specs, producing a single flat dictionary |
| **DeepDiff** | A Python library for comparing nested dictionaries — used by the diff engine to find structural changes |
| **genson** | A Python library that infers a JSON Schema by sampling real JSON data |
| **Compatibility score** | A 0–100 metric produced by the diff engine; 100 means no breaking changes |
