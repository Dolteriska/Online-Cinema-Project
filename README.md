# Online Cinema

**Online Cinema** is a backend platform for an online movie theater that lets users register, browse a movie catalog, add movies to favorites and cart, place orders, and pay for purchases online. The project is implemented as a REST API on **FastAPI** and follows a modular architecture with a clear separation of domains: accounts, movies, shopping cart, orders, and payments.

Repository: [Dolteriska/Online-Cinema-Project](https://github.com/Dolteriska/Online-Cinema-Project)

---

## Table of Contents

- [Project Overview](#project-overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [Installation and Running](#installation-and-running)
- [Environment Variables](#environment-variables)
- [Database Migrations](#database-migrations)
- [API Documentation](#api-documentation-work-in-progress)
- [Testing](#testing)
- [CI/CD](#cicd-planned)

---

## Project Overview

Online Cinema is a digital platform that allows users to select, watch, and purchase access to movies over the internet. The project covers the full lifecycle of such a service: from user registration and authentication to paying for orders via Stripe.

The project is split into five core modules:

1. **Accounts** — registration, authentication, roles, and profile management.
2. **Movies** — movie catalog, genres, actors, directors, comments, and ratings.
3. **Shopping Cart** — purchase cart.
4. **Orders** — order placement.
5. **Payments** — order payment via Stripe.

---

## Features

### 1. Accounts and Authorization

- User registration by email with an account activation email (the link is valid for 24 hours).
- Ability to resend the activation email if the previous link has expired.
- Periodic removal of expired activation tokens via **Celery Beat**.
- Login and logout using a pair of **JWT tokens** (access + refresh).
- Access token renewal via the refresh token.
- Logging out invalidates the refresh token.
- Password change with the old password, plus password reset via email (without knowing the old password).
- Password complexity validation.
- Three user groups with different access levels: **User**, **Moderator**, **Admin**.
- Admins can change a user's group and manually activate accounts.
- Avatar storage via **MinIO** (S3-compatible object storage), served through temporary presigned URLs.

### 2. Movies

- Paginated movie catalog.
- Detailed movie descriptions: genres, actors, directors, certification, IMDb rating.
- Likes/dislikes, comments, and notifications about replies to comments.
- 10-point movie rating scale.
- Filtering (release year, IMDb rating, etc.) and sorting (price, release date, popularity).
- Full-text search by title, description, actors, and directors.
- Favorites list with support for search, filtering, and sorting.
- List of genres with the number of movies in each.
- CRUD operations on movies, genres, and actors for moderators.
- Prevents deleting a movie if it has already been purchased by at least one user.

### 3. Shopping Cart

- Add/remove movies from the cart.
- Prevents adding an already purchased movie again.
- View cart contents (title, price, genre, release year).
- Pay for all movies in the cart at once.
- Automatically moves paid movies to the "Purchased" list.
- Fully clear the cart.
- Moderators can view the contents of users' carts.

### 4. Orders

- Place an order based on the cart contents.
- Excludes unavailable movies from the order with a notification to the user.
- View order history with statuses: **pending**, **paid**, **canceled**.
- Cancel an order before payment; after payment, cancellation is only possible via a refund request.
- Email confirmation after successful payment.
- Moderators can filter orders by user, date, and status.

### 5. Payments

- Payment via **Stripe**.
- Payment confirmation on the website and via email.
- User payment history (date, amount, status).
- Transaction validation through payment system webhooks.
- Order status update upon successful payment.
- Moderators can view all payments filtered by user, date, and status.

---

## Tech Stack

| Category | Technologies |
|---|---|
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| ORM / Migrations | SQLAlchemy, Alembic |
| Async Tasks | Celery, Celery Beat |
| Message Broker / Cache | Redis |
| File Storage | MinIO (S3-compatible) |
| Payments | Stripe |
| Authentication | JWT (access/refresh tokens) |
| Dependency Management | Poetry |
| Containerization | Docker, Docker Compose |
| API Documentation | Swagger / OpenAPI 3.0+ |
| CI/CD | GitHub Actions |
| Testing | Pytest |

---

## Project Structure

```
Online-Cinema-Project/
├── .github/
│   └── workflows/
│       └── ci.yml              # CI pipeline (lint, type-check, tests)
├── alembic/                     # Database migrations
├── src/                          # Application source code (FastAPI)
│   ├── config/                    # Settings and dependencies
│   ├── database/                   # Models, DB connection
│   ├── exceptions/                  # Custom exception classes
│   ├── routes/                       # API endpoints by domain
│   ├── schemas/                       # Pydantic schemas
│   ├── security/                       # JWT, hashing, permissions
│   ├── services/                        # Business logic (email, storage, etc.)
│   ├── stripe/                           # Stripe payment integration
│   ├── tasks/                             # Celery tasks
│   ├── __init__.py
│   ├── celery_app.py                       # Celery application setup
│   └── main.py                              # FastAPI application entry point
├── tests/                        # Test suite
│   ├── functional/                 # End-to-end user journey tests
│   │   └── test_user_journey.py
│   ├── integration/                 # Endpoint + DB integration tests
│   │   ├── test_admin_access.py
│   │   ├── test_auth.py
│   │   ├── test_cart_and_orders.py
│   │   └── test_movies.py
│   ├── unit/                          # Unit tests (schemas, security, validators)
│   │   ├── test_schemas_validation.py
│   │   ├── test_security.py
│   │   └── test_validators.py
│   ├── conftest.py                     # Shared pytest fixtures
│   └── factories.py                     # Test data factories
├── .env.sample                   # Sample environment variables file
├── .flake8                        # Flake8 configuration
├── .gitignore
├── Dockerfile                      # Application Docker image (installs deps via Poetry)
├── docker-compose.yml                # Service orchestration (FastAPI, PostgreSQL, Redis, Celery, MinIO)
├── entrypoint.sh                      # Container startup script
├── alembic.ini                         # Alembic configuration
├── pyproject.toml                       # Project dependencies and configuration (Poetry)
├── poetry.lock                           # Locked dependency versions
└── README.md
```

---

## Database Schema

The project uses five logical groups of tables:

- **Accounts**: `users`, `user_groups`, `user_profiles`, `activation_tokens`, `password_reset_tokens`, `refresh_tokens`.
- **Movies**: `movies`, `genres`, `stars`, `directors`, `certifications` + association tables `movie_genres`, `movie_directors`, `movie_stars`.
- **Shopping Cart**: `carts`, `cart_items`.
- **Orders**: `orders`, `order_items`.
- **Payments**: `payments`, `payment_items`.

- Accounts DB Schema: (https://dbdiagram.io/d/Accounts-app-675ef6bee763df1f00fd8ed1)
- Movies DB Schema: (https://dbdiagram.io/d/Movies-app-675f03b9e763df1f00fe4769)
- Shoppin Cart DB Schema: (https://dbdiagram.io/d/Cart-app-675f0d88e763df1f00fed027)
- Orders DB Schema: (https://dbdiagram.io/d/Order-app-675f141ce763df1f00ff29cb)
- Payment DB Schema: (https://dbdiagram.io/d/Payment-app-675f1a65e763df1f00ff70c6)

Key relationships:

- `User` 1:1 `Cart`, `User` 1:1 `UserProfile`, `User` 1:n `Order`/`Payment`.
- `Movie` n:n `Genre`/`Star`/`Director`, `Movie` n:1 `Certification`.
- `Order` 1:n `OrderItem`, `Payment` 1:n `PaymentItem`.

---

## Installation and Running

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ and [Poetry](https://python-poetry.org/docs/#installation) (for local development without containers)

### Running with Docker Compose

```bash
git clone https://github.com/Dolteriska/Online-Cinema-Project.git
cd Online-Cinema-Project

cp .env.sample .env
# fill in the environment variables in .env

docker compose up --build
```

This command starts all required services: **FastAPI**, **PostgreSQL**, **Redis**, **Celery worker**, **Celery Beat**, **MinIO**, and **MailHog**.
Database migrations are applied automatically on container start via `entrypoint.sh` — no manual `alembic upgrade head` step is needed here.

The application will be available at: `http://localhost:8000`

### Running Locally with Poetry (without Docker)

Poetry manages the virtual environment for you automatically.

```bash
git clone https://github.com/Dolteriska/Online-Cinema-Project.git
cd Online-Cinema-Project

poetry install

cp .env.sample .env
# fill in the environment variables (point DB/Redis/MinIO hosts to localhost)

poetry run alembic upgrade head
poetry run uvicorn src.main:app --reload
```

> **Note:** Running the app fully locally without Docker also requires PostgreSQL, Redis, and MinIO to be available (either installed locally or run separately via `docker compose up db redis minio mailhog`).

---

## Environment Variables

The full list of variables is in `.env.sample`. Main configuration groups:

- **PostgreSQL** connection parameters.
- **Redis** parameters (Celery broker).
- **JWT** settings (secret keys, access/refresh token lifetimes).
- Mail server settings for sending activation and password reset emails.
- **Stripe** keys for payment processing.
- **MinIO** (S3) connection settings for storing avatars and other files (`MINIO_ENDPOINT_INTERNAL`, `MINIO_ENDPOINT_PUBLIC`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET_NAME`).

---

## Database Migrations

The project uses **Alembic** to manage the database schema.

> In the Docker Compose setup, migrations run automatically on every container start via `entrypoint.sh`. The commands below are for manual use (local development without Docker, or creating new migrations).

```bash
# Create a new migration
poetry run alembic revision --autogenerate -m "description of changes"

# Apply migrations
poetry run alembic upgrade head

# Roll back the last migration
poetry run alembic downgrade -1
```

Inside Docker, the same commands are available via:
```bash
docker compose exec app alembic upgrade head
```

---

## API Documentation (work in progress)

Once the application is running, interactive documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

Access to the documentation is restricted and available only to authorized users (work in progress).

---

## Testing

Tests are run with **Pytest**:

```bash
poetry run pytest
poetry run pytest --cov=src        # with a coverage report
```

Inside Docker:
```bash
docker compose exec app pytest
```

Test coverage includes:

- Unit tests (data validation, utility functions, business rules).
- Integration tests (interaction between endpoints and the database, JWT authentication).
- Functional tests of end-to-end scenarios (registration, login, movie filtering, order placement).

---

## CI/CD (planned)

Automation is configured via **GitHub Actions** and includes:

- Dependency installation via **Poetry**.
- Code style checks (`flake8`).
- Type checking (`mypy`).
- Running tests (`pytest`) with a coverage report.
- Automatic deployment to **AWS EC2** after all checks pass and a pull request is merged into the main branch.

---

## Author

The project was developed by [Dolteriska](https://github.com/Dolteriska) as part of an educational project for building a backend platform for an online cinema.
