# Backend — Setup & Project Overview

This document explains how to create a virtual environment, install dependencies, run the FastAPI app, and describes each folder in the project so new contributors can get started quickly.

## Prerequisites
- Python 3.11+ installed and available as `python3` (or `python3.13` on this system).
- `pip` available for installing packages.

## Create a virtual environment
Run the following to create a venv named `backend_venv` in the current folder:

```bash
python3 -m venv backend_venv
```

Activate the venv (macOS / Linux):

```bash
source backend_venv/bin/activate
```

On Windows (PowerShell):

```powershell
.\\backend_venv\\Scripts\\Activate.ps1
```

Note: this repository includes a `backend_venv` directory. You can either use that existing environment or create a new one as shown above. Creating your own venv keeps your setup reproducible.

## Install dependencies
If a `requirements.txt` is present, install with:

```bash
pip install -r requirements.txt
```

To generate `requirements.txt` from your active environment (after installing everything you need):

```bash
pip freeze > requirements.txt
```

## Environment variables
This project typically uses a `.env` file for secrets and runtime config (database URL, JWT keys, etc.). Create a `.env` in the repo root and add values required by `core/config.py` (or the code that reads env vars). Example keys you might need:

- `DATABASE_URL`
- `SECRET_KEY` or `JWT_SECRET`
- `ENV` (development / production)

Load `.env` automatically by the app (the codebase likely uses `python-dotenv`).

## Running the app (development)
With the venv activated and dependencies installed, run:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

If `uvicorn` is installed inside `backend_venv`, use the venv binary path, e.g. `backend_venv/bin/uvicorn main:app --reload`.

## Quick checks and tests
- Ensure the venv is active: `which python` (should point inside `backend_venv`)
- Visit `http://127.0.0.1:8000/docs` for the automatic FastAPI docs (if app is running).

## Project structure and what each folder/file does

- `main.py` — Application entrypoint where the FastAPI `app` instance is created and middleware/routers are mounted.
- `__init__.py` — Package marker files.

- `api/` — HTTP API layer. Contains dependency injection helpers and versioned routes.
  - `api/deps.py` — Common dependency providers for routes.
  - `api/v1/routes/` — Route modules (for v1 of the public API). Example: `auth.py` contains authentication endpoints.

- `core/` — Core app configuration and low-level helpers.
  - `core/config.py` — Centralized configuration (reads env vars, default settings).
  - `core/database.py` — Database connection setup and session helpers.
  - `core/security.py` — Security helpers (password hashing, token helpers).

- `models/` — ORM models (database table definitions). Example: `user.py` defines the `User` model.

- `schemas/` — Pydantic models for request/response validation and serialization (e.g., `auth.py` schemas for login/signup).

- `repositories/` — Data access layer. Encapsulates database queries and persistence logic (e.g., `user_repo.py`).

- `services/` — Business logic layer. Implements higher-level operations (e.g., `auth_service.py` for login, token creation).

- `policies/` — Authorization and business-rule policies (if present) used by services or route guards.

- `utils/` — Utility functions and helpers used across the codebase.

- `migrations/` — Database migration files (if the project uses Alembic or similar). Keep migrations here.

- `backend_venv/` — A bundled virtual environment. You can use it directly, but creating your own `backend_venv` is recommended.

## Notes & best practices
- Prefer creating your own venv to avoid modifying the included `backend_venv`.
- Keep secrets out of the repository — use `.env` files or a secret manager and add `.env` to `.gitignore`.
- Add or update `requirements.txt` after installing packages so other contributors can reproduce your environment.

## Helpful commands summary

```bash
# create venv
python3 -m venv backend_venv
source backend_venv/bin/activate

# install deps
pip install -r requirements.txt

# run dev server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# freeze current env
pip freeze > requirements.txt
```

---
If you'd like, I can also generate a `requirements.txt` from the existing `backend_venv` or tune the README to include exact env variable names expected by `core/config.py`.
