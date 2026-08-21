# Job Scraper

A FastAPI backend for storing and managing scraped job postings, companies, contacts, and skills.

## Tech Stack

- **Language:** Python 3.12+
- **Framework:** FastAPI
- **ORM:** SQLAlchemy 2.0
- **Migrations:** Alembic
- **Database:** PostgreSQL (also supports MySQL, SQL Server)
- **Auth:** JWT (PyJWT + Argon2 password hashing)
- **Containerization:** Docker + Docker Compose
- **Package Manager:** Poetry

## Project Structure

```
src/
├── main.py                    # FastAPI app entry point
├── config.py                  # Environment variables & logging
├── database.py                # SQLAlchemy engine, session, Base
├── jwt_auth/                  # Authentication module
│   ├── api.py                 # Auth routes (login, refresh, logout, profiles)
│   ├── models.py              # User, RefreshToken, AccessTokenBlacklist
│   └── schema.py              # Pydantic request/response models
├── jobs/                      # Job posting module
│   ├── api.py                 # Job listing route (filter, sort, paginate)
│   ├── models.py              # Job, JobSkill, JobRequiredSkill, JobPreferredSkill
│   └── schema.py
├── company/                   # Company module
│   ├── models.py              # Company
│   ├── api.py
│   └── schema.py
├── contact/                   # Contact module
│   ├── models.py              # Contact
│   ├── api.py
│   └── schema.py
├── scraper/                   # Scrape run tracking
│   ├── models.py              # ScrapeRun
│   ├── api.py
│   └── schema.py
├── services/                  # Business logic layer
│   ├── jwt_auth/              # Auth services & dependencies
│   ├── company/               # create_company
│   ├── conatact/              # create_contact
│   ├── jobs/                  # get_posted_jobs
│   └── scraper/               # create_scrape_run
└── utils/
    ├── jwt_handler.py         # Token creation & decoding
    └── password_helper.py     # Argon2 hash/verify
```

## Prerequisites

- Python 3.12+
- Poetry
- PostgreSQL (or MySQL / SQL Server)
- Docker & Docker Compose (optional)

## Setup & Installation

### Local Development

```bash
# Install dependencies
poetry install

# Create .env from example
cp .env.example .env
# Edit .env with your database URL and JWT secret

# Run migrations
alembic upgrade head

# Start the server
uvicorn src.main:app --reload
```

API docs available at `http://localhost:8000/docs`

### Docker

```bash
# Build and start
docker compose up --build
```

The entrypoint automatically waits for the database, runs migrations, and starts the server on port `8000`.

> **Note:** The Docker setup expects an external database. Update `DATABASE_URL` in `.env` to point to `host.docker.internal` instead of `localhost`.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | Database connection URL |
| `JWT_SECRET_KEY` | Yes | — | Secret key for signing JWT tokens |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | Access token TTL (minutes) |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | Refresh token TTL (days) |
| `LOG_LEVEL` | No | `INFO` | Logging level |

### Supported Database URLs

```
# PostgreSQL
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/dbname

# MySQL
DATABASE_URL=mysql+mysqlconnector://user:password@localhost:3306/dbname

# SQL Server
DATABASE_URL=mssql+pyodbc://user:password@localhost:1433/dbname?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes
```

## Database

### Migrations

```bash
# Apply all migrations
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "description"
```

### Migration History

1. `b1987a2a1796` — Create users table
2. `cead0912f46d` — Add refresh token table
3. `a3d7f5b8c1e2` — Add role column and access token blacklist
4. `81c9b23b607a` — Create jobs, skills, contacts, companies, scrape_runs tables

## API Endpoints

### Authentication (`/auth`)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/login` | None | Login with email & password |
| POST | `/auth/refresh` | None | Get new access token using refresh token |
| POST | `/auth/logout` | None | Revoke refresh token & blacklist access token |
| GET | `/auth/profile` | Bearer token | Get current user profile |
| GET | `/auth/admin/profile` | Bearer + admin role | Admin-only profile |
| GET | `/auth/user/profile` | Bearer + user role | User-only profile |

### Jobs (`/api`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/list_jobs` | None | List jobs with filter, sort & pagination |

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `page` | int | Page number (default: 1) |
| `per_page` | int | Records per page (default: 10) |
| `filter_column` | string | Filter by: `title`, `location`, `employment_type`, `work_type`, `source`, `company_id` |
| `filter_value` | string | Value to filter on |
| `sort_column` | string | Sort by: `title`, `location`, `created_at`, `updated_at`, `min_salary`, `max_salary` |
| `sort_by` | string | `asc` or `desc` |

### Health Check

| Method | Path | Description |
|---|---|---|
| GET | `/health_check` | Returns service status |

## Data Models

| Table | Description |
|---|---|
| `users` | Application users with roles (admin/user) |
| `refresh_tokens` | Stored refresh tokens for JWT rotation |
| `access_token_blacklist` | Blacklisted access token JTIs |
| `scrape_runs` | Tracks each scraping execution (status, records count, exceptions) |
| `companies` | Company details linked to scrape runs |
| `contacts` | Contact persons (poster/hiring manager) linked to companies |
| `jobs` | Job postings with salary, experience, skills, and company/contact references |
| `job_skills` | Shared skill dictionary (e.g., Python, SQL, Tableau) |
| `job_required_skills` | Junction table linking jobs to required skills |
| `job_preferred_skills` | Junction table linking jobs to preferred skills |

### Entity Relationships

```
ScrapeRun ──1:N──> Company ──1:N──> Contact
ScrapeRun ──1:N──> Job ──N:1──> Company
                  Job ──N:1──> Contact (posted_by)
                  Job ──N:M──> JobSkill (via job_required_skills)
                  Job ──N:M──> JobSkill (via job_preferred_skills)
```

## Running Tests

```bash
poetry run pytest -v
```

Tests use mocked services and an in-memory database — no external database required.
