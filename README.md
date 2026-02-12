## Noree Fun Tickets – Microservices Monorepo

This repository is a **monorepo** that combines several Python microservices used for the Noree Fun Tickets system. It was migrated from multiple GitLab projects into a single GitHub repository using `git subtree`, preserving each service’s history.

### Repository structure

All services live under the `services/` directory:

- `services/admin` – Admin / management API and related functionality.
- `services/booking-coordinator` – Orchestrates ticket booking workflows.
- `services/booking-worker` – Background worker for booking-related jobs.
- `services/notifications` – Handles notifications (e.g. email/SMS/push).
- `services/payment` – Payment processing / integration logic.
- `services/ticket-booking` – Public-facing ticket booking APIs and logic.

Each service is an independent Python app with its own:

- `src/` source code
- `tests/` (where present)
- `requirements.txt`
- `Dockerfile`

### Development prerequisites

- **Python** (3.10+ recommended)
- **Docker** and **Docker Compose** (for container-based development)
- **Git**

Each service can be developed and run independently; there is no strict requirement to run all services at once unless you are doing full-system testing.

### Getting started (per-service)

From the repository root:

```bash
cd services/admin           # or any other service
python -m venv .venv        # optional but recommended
source .venv/bin/activate   # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Then follow that service’s own documentation / `README.md` (if present) for how to run the app. Common patterns:

- `python -m src.app`
- Or a framework-specific command (e.g. Flask, FastAPI, etc.).

### Running with Docker

Each service has its own `Dockerfile`. From the repository root you can build and run an individual service, for example:

```bash
cd services/admin
docker build -t noree-admin .
docker run --rm -p 8000:8000 noree-admin
```

You can repeat this pattern for other services (changing the image name, port, and any environment variables as needed).

> **Note:** If you want, you can add a root-level `docker-compose.yml` later to orchestrate all services together. The current monorepo layout is compatible with that.

### Monorepo conventions

- **Service isolation**: Each service keeps its own dependencies (`requirements.txt`) and Dockerfile. Changes that affect only one service should usually touch only that service’s directory.
- **Cross-service changes**: When changing shared behavior (e.g. contracts between services), update all affected services in a single commit and describe the change clearly in the commit message.
- **CI config**: Original `.gitlab-ci.yml` files are retained inside each service for reference, but CI/CD is now expected to be configured on GitHub (e.g. using GitHub Actions) at the monorepo level.

### Working with history

Because this repository was created via `git subtree`:

- Each service’s commit history is preserved.
- You can use `git log -- services/<service-name>` to see just that service’s history, for example:

```bash
git log --oneline --graph -- services/admin
```

### Future improvements

Some useful next steps you can add over time:

- Root-level `docker-compose.yml` to run all services together.
- Root-level `.editorconfig` to standardize formatting across services.
- GitHub Actions workflows for tests and linting for each service.
- Centralized documentation (e.g. architecture diagrams, API contracts).

