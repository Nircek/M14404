# M14404

**A modular, domain-driven ASGI framework and ingestion service.**

`M14404` routes HTTP and WebSocket traffic based on subdomains rather than URL paths. Built on top of Starlette and Tortoise ORM, it allows you to add entirely new applications or actions to your service simply by creating a new file in the `subdomains/` directory. 

Currently optimized for lightweight, low-cost hosting behind Nginx on Alpine Linux.

## Key Features

* **Dynamic Subdomain Routing:** Automatically discovers and maps incoming `Host` headers to isolated handler classes.
* **Zero-Config ORM:** Tortoise ORM dynamically discovers database models specific to each subdomain and auto-generates schemas.
* **Native WebSockets:** First-class support for WebSocket connections alongside standard HTTP requests.
* **Modern Python Stack:** Written for Python 3.11+, typed with `mypy`, formatted with `ruff`, and managed entirely by `uv`.

## Local Development

Prerequisites: Python 3.11+ and [uv](https://github.com/astral-sh/uv).

1. **Install dependencies:**
   ```sh
   uv sync --all-extras --dev
    ```

2.  **Run tests:**

    ```sh
    uv run pytest
    ```

3.  **Start the local server:**

    ```sh
    uv run uvicorn M14404.main:app --host 0.0.0.0 --port 8000
    ```

You can test the routing locally by passing a custom host header. For example:
`curl -H "Host: www.yourdomain.local" http://127.0.0.1:8000/`

## Production Deployment

`M14404` is designed to be easily deployed on Alpine Linux using OpenRC and Nginx.

A comprehensive, step-by-step installation guide—along with the required Nginx and OpenRC configuration files—can be found in [INSTALLATION.md](./INSTALLATION.md).


### Future Considerations for Production (High Scale & Many Subdomains)

Since you plan to run this on a production server with "really many subdomains," here is an unvarnished look at the bottlenecks and edge cases you will need to anticipate:

* **SQLite Concurrency and Write Locks:** You are logging *every* HTTP request and WebSocket message to SQLite (`www.py`). While SQLite is incredibly fast, it handles concurrency by locking the entire database for writes. If you have hundreds of subdomains generating traffic simultaneously, you will hit `database is locked` errors. You must ensure SQLite is operating in WAL (Write-Ahead Logging) mode, and you may eventually need to batch your logs or migrate to PostgreSQL if the write volume grows too high.
* **Database Schema Migrations:** Your app currently runs `Tortoise.generate_schemas()` on startup. This is great for development, but in production, if a subdomain updates a model (e.g., changes a column type or adds a foreign key), `generate_schemas()` will not safely alter existing tables. You will need to integrate a migration tool like Aerich before you have production data you care about losing.
* **Dynamic Module Reloading (Zero-Downtime Goals):** To achieve your goal of adding subdomains without a restart, you'll need to drop the `@lru_cache` and implement a file watcher (like `watchfiles`) or an admin endpoint that triggers a cache flush and an `importlib.reload()`. Be very careful here: reloading Python modules in a running async process can lead to memory leaks or orphaned database connections.
* **Global Rate Limiting:** A catch-all wildcard setup makes you highly vulnerable to DDoS attacks or aggressive web scrapers scanning random subdomains. You should implement rate limiting at the Nginx level or add a Starlette middleware to throttle IPs that spam non-existent subdomains.
* **Memory Bloat:** If you eventually have 500 subdomains, your Starlette app will hold 500 module imports in memory. Since Python doesn't aggressively garbage collect imported modules, keep an eye on your server's RAM usage as the project scales.
* **ORM Connection Limits:** When a WebSocket connection remains open, it might hold onto database resources or memory depending on how often it writes logs. Ensure your Tortoise connection pool is configured to handle the maximum number of simultaneous active WebSockets you expect. 
