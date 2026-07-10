# Vehicle Service Shop API

A FastAPI-based backend application for managing an auto repair shop. It provides comprehensive APIs to manage customer visits, quotes, work orders, service bays, technicians, and billing.

## Technology Stack

- **Framework:** FastAPI
- **Database:** PostgreSQL (with SQLAlchemy asyncpg driver)
- **Migrations:** Alembic
- **Testing:** Pytest & HTTPX
- **Security:** JWT Authentication, Role-Based Access Control (RBAC), Secure headers middleware, Rate limiting (SlowAPI)
- **Logging:** Structured JSON Logger

## Features

- **RBAC (Role-Based Access Control):** Permissions structured for roles: `manager`, `advisor`, `technician`, and `customer`.
- **Customers & Vehicles:** Manage customer profiles and vehicle information.
- **Appointments & Visits:** Handle appointments booking and customer check-in/out.
- **Job Execution:** Manage Work Orders and specific tasks/labor via Line Items.
- **Shop Resources:** Allocate technicians and manage shop service bays.
- **Billing & Financials:** Create Quotes, generate Invoices, record pre-payment Deposits, and process client Payments.

## Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL database (or Docker installed to run it via container)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Affan1316/vehicle-service-shop-api.git
   cd vehicle-service-shop-api
   ```

2. **Set up environment variables:**
   Copy the example environment file and configure your credentials:
   ```bash
   cp .env.example .env
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the database:**
   If you have Docker running, start the PostgreSQL container:
   ```bash
   docker compose up -d db
   ```

5. **Run database migrations:**
   ```bash
   alembic upgrade head
   ```

6. **Start the application server:**
   ```bash
   uvicorn app.main:app --reload
   ```
   The interactive documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

## Running Tests

Verify everything runs successfully using pytest:
```bash
pytest
```
