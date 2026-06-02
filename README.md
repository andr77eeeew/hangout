# Hangout

Hangout is an open-source backend and Telegram bot for organizing online and offline group activities around games,
shared interests, and small communities.

The project is currently in active development. It focuses on the core coordination layer for a community platform: user
accounts, profiles, activity creation, membership requests, real-time activity chat, notifications, Telegram account
linking, and moderation workflows.

## Features

- User registration, login, refresh tokens, and password updates
- Ban enforcement across login, token refresh, access tokens, and WebSocket access
- User profiles with avatar, banner, bio, tags, and Telegram ID fields
- Activity feed with cursor pagination and filters
- Online and offline activities with category-specific validation
- Open and approval-based membership flows
- Activity member management: approve, reject, kick, leave, and list members
- Real-time activity chat over WebSocket
- Chat history with cursor pagination
- WebSocket rate limiting and structured message validation
- User reports with open, in-review, resolved, and dismissed states
- Moderator report handling, report history, and ban/unban actions
- Notification preferences for membership updates, activity reminders, tag matches, and report updates
- Telegram account linking with verification codes
- Telegram bot commands for linking, status, unlinking, and notification preferences
- Telegram notifications for membership changes, activity reminders, tag matches, and report updates
- RAWG game search and cover fetching through Celery tasks
- Image processing and S3-compatible object storage
- Scheduled jobs with Celery Beat
- PostgreSQL migrations with Alembic
- MongoDB collections and startup index management
- Docker Compose setup for local development
- Pytest coverage for auth, activities, chat, membership, profiles, tags, RAWG, MongoDB helpers, Telegram linking,
  notifications, reports, bans, and bot handlers

## Tech Stack

- Python 3.12
- FastAPI
- aiogram 3
- SQLAlchemy async + Alembic
- PostgreSQL
- MongoDB
- Redis
- RabbitMQ
- Celery + Celery Beat
- MinIO / S3-compatible storage
- WebSockets
- Pytest
- Docker Compose

## Repository Structure

```text
.
+-- backend/
|   +-- app/
|   |   +-- api/          # FastAPI routers
|   |   +-- core/         # configuration, db clients, auth, storage, ws helpers
|   |   +-- models/       # SQLAlchemy models
|   |   +-- schemas/      # Pydantic schemas and validators
|   |   +-- services/     # business logic
|   |   +-- tasks/        # Celery tasks
|   +-- migrations/       # Alembic migrations
|   +-- tests/            # backend test suite
+-- telegram_bot/
|   +-- bot/
|   |   +-- handlers/     # aiogram command and callback handlers
|   |   +-- keyboards/    # inline keyboards
|   |   +-- middlewares/  # bot auth/linking helpers
|   |   +-- api_client.py # internal backend API client
|   +-- tests/            # bot handler tests
+-- docker-compose.yaml
+-- .env.example
```

## Getting Started

### Prerequisites

- Docker
- Docker Compose
- A Telegram bot token if you want to run Telegram features
- A RAWG API key if you want game cover fetching

### 1. Clone the repository

```bash
git clone https://github.com/andr77eeeew/hangout.git
cd hangout
git checkout feature/bot
```

### 2. Configure environment variables

Copy the example environment file:

```bash
cp .env.example .env
```

Then edit `.env` and replace placeholder secrets and passwords.

Important variables:

- `DATABASE_URL`
- `MONGO_URL`
- `SECRET_KEY`
- `BUCKET_*`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `RAWG_API_KEY`
- `INTERNAL_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `BACKEND_INTERNAL_URL`
- `CORS_ORIGINS`

`RAWG_API_KEY` is only required for game cover fetching.

`TELEGRAM_BOT_TOKEN` is required for Telegram bot commands and Telegram notifications.

`INTERNAL_API_KEY` is used by internal backend endpoints for the Telegram bot. Keep it secret in non-local environments.

### 3. Start the stack

```bash
docker compose up --build
```

The backend container runs database migrations on startup and then starts Uvicorn.

Docker Compose starts:

- FastAPI backend
- Celery worker
- Celery Beat scheduler
- PostgreSQL
- MongoDB
- Redis
- RabbitMQ
- MinIO
- Telegram bot

### 4. Open the API

- API root: `http://localhost:8000/`
- Health check: `http://localhost:8000/health`
- Swagger UI: `http://localhost:8000/docs`

## Telegram Bot

The Telegram bot is implemented as a separate service in `telegram_bot/` using aiogram 3. It communicates with the
backend through internal API endpoints protected by `INTERNAL_API_KEY`.

Available commands:

- `/start` - welcome message and linking instructions
- `/help` - command list
- `/link` - generate a 6-digit code to link Telegram with a Hangout account
- `/status` - show linked Hangout account status
- `/notifications` - view and update notification preferences
- `/unlink` - unlink Telegram from Hangout

The backend supports Telegram-related internal endpoints under:

```text
/internal/telegram
```

## Notifications

Hangout supports notification preferences for:

- Membership updates
- Activity reminders
- Tag subscription matches
- Report updates

Notifications can be delivered through Telegram when the user has linked their Telegram account and enabled the relevant
preference.

Scheduled reminders are handled by Celery Beat and Celery tasks.

## Moderation

Hangout includes moderation workflows for community safety:

- Users can submit reports
- Moderators can list, take, resolve, or dismiss reports
- Moderators can view report history for a user
- Reports can optionally lead to user bans
- Users can be banned and unbanned
- Bans are enforced in authentication, refresh/access token checks, and WebSocket flows

Main moderation API areas:

```text
/reports
/users/{user_id}/ban
/users/{user_id}/unban
```

## Development

Install backend dependencies locally if you want to run backend tests outside Docker:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

On Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
```

Run backend tests:

```bash
pytest
```

Run backend type checks:

```bash
mypy app
```

Install Telegram bot dependencies locally:

```bash
cd telegram_bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
cd telegram_bot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run bot tests:

```bash
pytest
```

## API Areas

- `/auth` - authentication and token flows
- `/user` - current user profile, avatar, banner, password, favorite tags, and notification preferences
- `/users` - user moderation actions such as ban and unban
- `/activities` - activity creation, feed, updates, deletion, membership, and chat
- `/games` - game search and related metadata
- `/reports` - report submission and moderation workflow
- `/internal/telegram` - internal Telegram bot integration endpoints
- `/health` - service health check

## Security Notes

Hangout includes authentication, password changes, refresh tokens, file uploads, WebSocket chat, internal service
authentication, Telegram account linking, notification delivery, membership permissions, reports, bans, and rate
limiting.

Security reviews are especially valuable around:

- Authorization boundaries between creators, members, moderators, banned users, and regular users
- Ban enforcement across REST and WebSocket paths
- Internal API authentication for Telegram bot endpoints
- Telegram account linking and unlinking flows
- File upload validation and storage access
- Password and token lifecycle
- Activity membership state transitions
- Report and moderation workflows
- WebSocket authentication and abuse handling
- Input validation for activity categories, filters, reports, and chat payloads

Please do not report security issues publicly. Contact the repository owner directly.

## Roadmap

- Frontend client for browsing and joining activities
- Better contributor documentation
- CI pipeline for tests and type checks
- More complete API documentation
- Expanded moderation tooling
- Production deployment guide
- Security policy and responsible disclosure process
- Notification delivery improvements

## Contributing

Contributions are welcome. Good first areas include tests, documentation, API validation, security hardening, Telegram
bot UX, and frontend integration work.

Suggested workflow:

1. Fork the repository
2. Create a feature branch
3. Add or update tests when behavior changes
4. Run the relevant test suite
5. Open a pull request with a clear description

## License

This project is licensed under the MIT License. See `LICENSE` for details.
