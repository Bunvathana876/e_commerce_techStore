# 🛍️ Full-Stack E-Commerce Platform

[![Next.js](https://img.shields.io/badge/Next.js-16.3-black?style=for-the-badge&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Flutter](https://img.shields.io/badge/Flutter-3.x-02569B?style=for-the-badge&logo=flutter)](https://flutter.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker)](https://www.docker.com/)

A modern, production-ready, full-stack E-Commerce platform comprising a **Flutter Mobile App**, a **Next.js 16 Admin Dashboard**, and a high-performance **FastAPI REST Backend** backed by **PostgreSQL 16**.

---

## 📑 Table of Contents

- [Overview](#-overview)
- [System Architecture](#-system-architecture)
- [Documentation Hub](#-documentation-hub)
- [Key Features](#-key-features)
  - [Mobile Application (Customer-Facing)](#-mobile-application-customer-facing)
  - [Web Application (Admin & Merchant Portal)](#-web-application-admin--merchant-portal)
  - [Backend & REST API Engine](#-backend--rest-api-engine)
- [Tech Stack](#-tech-stack)
- [Quick Start Guide](#-quick-start-guide)
  - [Prerequisites](#prerequisites)
  - [One-Click Setup with Docker](#one-click-setup-with-docker)
  - [Running the Flutter Mobile App](#running-the-flutter-mobile-app)
- [Service Ports & Endpoints](#-service-ports--endpoints)
- [Default Demo Credentials](#-default-demo-credentials)
- [Project Directory Structure](#-project-directory-structure)
- [API Documentation](#-api-documentation)
- [Manual Setup (Without Docker)](#-manual-setup-without-docker)
- [Testing](#-testing)
- [License](#-license)

---

## 🌟 Overview

This repository is an end-to-end multi-platform e-commerce solution engineered for scalability, ease of development, and seamless multi-channel commerce:

1. **Mobile App (`mobile-app`)**: Native-feel cross-platform shopping experience built with Flutter and Provider state management.
2. **Web Portal (`web-app`)**: Full-featured admin back-office dashboard built with Next.js 16 (App Router), Tailwind CSS, and Lucide icons.
3. **Backend API (`backend`)**: Fast, asynchronous REST API powered by FastAPI, SQLAlchemy ORM, Alembic migrations, and JWT bearer authentication.
4. **Data Infrastructure**: Containerized PostgreSQL 16 database paired with pgAdmin 4 for visual database management.

---

## 🏛️ System Architecture

```mermaid
graph TD
    subgraph Clients
        Mobile[📱 Flutter Mobile App<br/>iOS & Android]
        Web[💻 Next.js 16 Web Portal<br/>Admin & Merchant Dashboard]
    end

    subgraph "Backend Services (Docker)"
        API[⚡ FastAPI REST API Engine<br/>Port :8000]
        Docs[📖 Interactive OpenAPI / Swagger<br/>/docs & /redoc]
    end

    subgraph "Storage & Tooling (Docker)"
        DB[(🐘 PostgreSQL 16 DB<br/>Port :5433)]
        PGA[📊 pgAdmin 4 Management UI<br/>Port :5050]
        Static[📁 Media & Asset Uploads]
    end

    Mobile -->|REST JSON + JWT| API
    Web -->|REST JSON + JWT| API
    API -->|SQLAlchemy ORM| DB
    API -->|Save / Serve Media| Static
    PGA -->|Manage DB| DB
```

---

## 📚 Documentation Hub

All engineering documentation, architectural specifications, runbooks, and roadmaps are organized under the [`docs/`](docs/README.md) directory:

| Directory | Purpose | Key Documents |
|---|---|---|
| [**`docs/architecture/`**](docs/architecture/) | Domain models, marketplace design, and UI/UX specifications | [Marketplace Plan](docs/architecture/MARKETPLACE_ARCHITECTURE_PLAN.md), [Storefront Redesign](docs/architecture/STOREFRONT_UI_REDESIGN_PLAN.md) |
| [**`docs/deployment/`**](docs/deployment/) | Production runbooks, Docker Compose setups, security audits & hardening | [VPS Runbook](docs/deployment/VPS_DEPLOYMENT_RUNBOOK.md), [Readiness Audit](docs/deployment/PRODUCTION_READINESS_AUDIT.md) |
| [**`docs/database-and-backend/`**](docs/database-and-backend/) | Database management, migrations, admin account bootstrapping, demo seeding | [Admin Bootstrap](docs/database-and-backend/ADMIN_BOOTSTRAP_PLAN.md), [Demo Seeding](docs/database-and-backend/DEMO_PRODUCT_SEED_PLAN.md) |
| [**`docs/planning/`**](docs/planning/) | Phased execution trackers (Frontend Separation, Phase 1 Hardening, Marketplace) | [Frontend Separation](docs/planning/frontend-separation/FRONTEND_SEPARATION_FINAL_REPORT.md), [Phase 1](docs/planning/phase-1/PHASE1_PROGRESS.md) |
| [**`docs/upgrade/`**](docs/upgrade/) | Modernization roadmaps, session-based auth security design, and plans | [Upgrade Roadmap](docs/upgrade/BLUE_PANDA_UPGRADE_ROADMAP.md), [Auth Security](docs/upgrade/PHASE_1C_AUTH_SECURITY_DESIGN.md) |
| [**`docs/STYLE_GUIDE.md`**](docs/STYLE_GUIDE.md) | Documentation standards, templates, alert boxes, and formatting rules | [Authoring Guide & Templates](docs/STYLE_GUIDE.md) |

> 💡 **Looking for the master index?** Visit the [**Central Documentation Hub (`docs/README.md`)**](docs/README.md).

---

## ✨ Key Features

### 📱 Mobile Application (Customer-Facing)
- **Authentication & Onboarding**: Clean Welcome, Login, and Sign-Up flows with real-time validation and persistent JWT token management.
- **Discovery & Search**: Hero discount carousels, categorized horizontal pills, search bar with debounce, and product filtering.
- **Product Details**: Multi-variant selector (editions, colors, sizes), dynamic image viewer, customer reviews, ratings summary, and stock checks.
- **Cart & Checkout**: Real-time price breakdown (subtotal, shipping, taxes, discount codes), interactive item count, and multi-step checkout (Credit Card, Apple Pay, Cash on Delivery).
- **Order Management & Tracking**: View active order statuses, past receipts, delivery timelines, and re-order functionality.
- **Favorites & Wishlist**: Bookmark favorite items with one-tap transfer to shopping cart.
- **In-App Notifications**: Real-time notifications for order updates, promotions, and account alerts.
- **User Profile**: Personal profile editing, shipping address book, payment methods, and theme/settings preferences.

### 🌐 Customer Storefront Website (`web-app` — `/`)
- **Editorial Hero & Flash Deals**: Multi-slide hero showcase, live countdown flash-sale drops, and 1-click claimable promo vouchers (`WELCOME10`, `SAVE20`, `SUMMER15`, `SUPER50`).
- **Interactive Shop & Instant Search (`⌘K`)**: Command-palette search dialog, multi-criteria catalog filtering (`/shop` by category, verified store, price ceiling, star rating, sale & stock status), and Grid/List toggle.
- **Product Details & Quick-View Modals**: Native top-layer quick-view dialogs, zoomable product stage (`/product/[id]`), option/size selectors, verified customer reviews, and live review submission.
- **Slide-Over Bag & Express Checkout**: Real-time `$100` free-shipping progress bar, server + local cart sync, promo code validation, autofill-optimized shipping address form, KHQR / Card / Apple Pay / COD payment options, and animated order confirmation receipts.
- **Customer Account & Live Order Tracking**: 4-step visual parcel status tracker (`/orders`), saved shipping address book, wishlist sync (`/wishlist`), notifications, and role-aware authentication synced with the Flutter Mobile App.

### 💻 Web Application (Admin & Merchant Portal — `/admin`)
- **Executive Analytics Dashboard**: KPI metrics (gross revenue, order counts, customer registrations, low-stock warnings) and sales trends.
- **Product & Catalog Management**: Create, edit, and organize products, multi-tier categories, inventory stock levels, and image gallery uploads.
- **Order Processing & Fulfillment**: Filter orders by status (`pending`, `processing`, `shipped`, `delivered`, `cancelled`), manage delivery dates, and track shipping.
- **Inventory & Supply Chain**: Stock balance monitor, stock alert notifications, supplier tracking, and batch updates.
- **Customer & Review Management**: Customer account lookup, purchase history inspection, and product review moderation (approve/reject/flag).
- **Merchant & Seller Management**: Multi-vendor / seller profiles, performance metrics, and commission settings.
- **Notification Center**: System-wide notifications, broadcast messages, unread counters, and mark-all-as-read controls.
- **Point of Sale (POS) Retail Register**: High-speed touch-friendly cashier interface (`/admin/pos`) with barcode input, category quick-pills, stock level alerts, instant cart adjustments, discount & tax calculation, order parking/holding, multiple payment methods (Cash with change calculator, Card terminal, QR Code), and 80mm thermal receipt printing (`window.print()`).
- **Security & Session Handling**: Smart JWT expiration checks, automatic stale-session logout, and route protection guards.

### ⚙️ Backend & REST API Engine
- **RESTful Endpoints**: Modular APIRouters covering `/auth`, `/products`, `/categories`, `/orders`, `/cart`, `/reviews`, `/notifications`, `/suppliers`, `/sellers`, `/analytics`, and `/upload`.
- **JWT Authentication & RBAC**: Secure password hashing with Passlib/Bcrypt, access token issuance, and role-based access control (`admin`, `seller`, `customer`).
- **Interactive Documentation**: Auto-generated Swagger UI (`/docs`) and ReDoc (`/redoc`) documentation with live request testing.
- **Database Migrations**: Alembic version-controlled database schema migrations.
- **Automatic Seeding**: Built-in seed data loader pre-populating essential categories, initial products, and test accounts.
- **Health Checks & CORS**: Configured health probe (`/health`) and customizable CORS headers for Flutter emulators and web clients.

---

## 🛠️ Tech Stack

| Layer | Technologies |
|---|---|
| **Mobile App** | Flutter 3.x, Dart 3.x, Provider, HTTP, Shared Preferences, Google Fonts |
| **Web Frontend** | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS, Lucide Icons, React Icons |
| **Backend API** | FastAPI, Python 3.12, Uvicorn, SQLAlchemy 2.0, Pydantic v2, Passlib, PyJWT |
| **Database** | PostgreSQL 16 Alpine, Alembic (Migrations) |
| **DevOps & Tools** | Docker, Docker Compose, pgAdmin 4 |

---

## 🚀 Quick Start Guide

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (v24.0+)
- [Flutter SDK](https://docs.flutter.dev/get-started/install) (v3.22+ for running the mobile app)
- [Node.js](https://nodejs.org/) (v20+ optional, for local web development without Docker)
- [Python](https://www.python.org/) (v3.12+ optional, for local backend development without Docker)

---

### One-Click Setup with Docker

Clone the repository and launch all backend and web services using the one-click launcher:

```bash
# 1. Clone repository
git clone https://github.com/<your-username>/e-commerce.git
cd e-commerce

# 2. Start all services using the launcher script
chmod +x run.sh
./run.sh
```

*Or run directly with Docker Compose:*

```bash
docker compose up --build -d
```

This starts:
- ✅ **PostgreSQL 16 Database** (Port `5433`)
- ✅ **FastAPI Backend** (Port `8000`)
- ✅ **Next.js Web Portal** (Port `3000`)
- ✅ **pgAdmin 4 UI** (Port `5050`)

---

### Running the Flutter Mobile App

Once the backend is up and running:

```bash
cd mobile-app

# 1. Install dependencies
flutter pub get

# 2. Check connected devices or launch simulator
flutter devices

# 3. Run the app
flutter run
```

> **Note for Android Emulators & Physical Devices:**
> - Android Emulator connects to localhost via `http://10.0.2.2:8000/api`
> - iOS Simulator connects to localhost via `http://127.0.0.1:8000/api`
> - Physical device over Wi-Fi: Update the API base URL in `mobile-app/lib/core/constants/api_constants.dart` with your machine's LAN IP (e.g., `http://192.168.1.X:8000/api`).

---

## 🌐 Service Ports & Endpoints

| Service | URL / Port | Description |
|---|---|---|
| **Customer Storefront Website** | [http://localhost:3000](http://localhost:3000) | Blue Panda User Shopping Website |
| **Admin & POS Portal** | [http://localhost:3000/admin/dashboard](http://localhost:3000/admin/dashboard) | Admin Back-Office & Retail POS |
| **FastAPI Backend** | [http://localhost:8000](http://localhost:8000) | Core REST API Endpoint |
| **Interactive Swagger UI** | [http://localhost:8000/docs](http://localhost:8000/docs) | OpenAPI interactive documentation |
| **Alternative API Docs** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | ReDoc API specifications |
| **Backend Health Check** | [http://localhost:8000/health](http://localhost:8000/health) | Container healthcheck endpoint |
| **pgAdmin 4 Dashboard** | [http://localhost:5050](http://localhost:5050) | PostgreSQL graphical management |
| **PostgreSQL Database** | `localhost:5433` | Database direct connection |

---

## 🔑 Default Demo Credentials (Local Development Only)

> [!WARNING]
> The credentials below are intended solely for local development and offline automated testing.
> In production environments (`ENVIRONMENT=production`), automatic demo seeding is strictly disabled,
> and a securely generated `JWT_SECRET_KEY` (minimum 32 characters) along with strong database credentials must be configured via environment variables.

The database is pre-seeded with default administrative and customer accounts for local development:

### Web Admin Portal
- **URL**: [http://localhost:3000/login](http://localhost:3000/login)
- **Email**: `admin@ecommerce.com`
- **Password**: `admin123`
- **Role**: `admin`

### Customer Mobile Account
- **Email**: `customer@ecommerce.com`
- **Password**: `password123`
- **Role**: `customer`

### Seller Center / Merchant Accounts
#### Seller 1 (Electronics Store)
- **Email**: `seller@ecommerce.com`
- **Password**: `seller123`
- **Role**: `seller`
- **Store Name**: TechGadgets Official Store
- **Owner**: Alex Rivera
- **Portal & POS**: [http://localhost:3000/seller](http://localhost:3000/seller) & [http://localhost:3000/seller/pos](http://localhost:3000/seller/pos)

#### Seller 2 (Fashion Boutique)
- **Email**: `seller2@ecommerce.com`
- **Password**: `seller123`
- **Role**: `seller`
- **Store Name**: Urban Chic Boutique
- **Owner**: Sarah Chen
- **Portal & POS**: [http://localhost:3000/seller](http://localhost:3000/seller) & [http://localhost:3000/seller/pos](http://localhost:3000/seller/pos)

### pgAdmin 4 Management UI
- **URL**: [http://localhost:5050](http://localhost:5050)
- **Login Email**: `admin@ecommerce.com`
- **Login Password**: `admin123`
- **Pre-configured Server**: `PostgreSQL 16 (Local)`
  - **Host**: `postgres`
  - **Port**: `5432`
  - **Database**: `ecommerce_db`
  - **User**: `ecommerce_user`
  - **Password**: `GoPassword_123!`

---

## 📁 Project Directory Structure

```text
e-commerce/
├── docs/                           # 📚 Centralized Documentation Hub
│   ├── architecture/               # System design, marketplace & UI/UX specs
│   ├── database-and-backend/       # Migrations, seeding & admin bootstrapping
│   ├── deployment/                 # VPS runbooks, readiness audits & prod configs
│   ├── planning/                   # Phase progress (frontend-separation, phase-1, marketplace)
│   ├── upgrade/                    # Upgrade roadmap & auth security design
│   ├── STYLE_GUIDE.md              # Documentation authoring standards & templates
│   └── README.md                   # Documentation table of contents
│
├── backend/                        # ⚡ FastAPI REST Backend Engine
│   ├── app/
│   │   ├── api/                    # APIRouters (auth, products, orders, etc.)
│   │   ├── core/                   # Security, JWT, config & dependencies
│   │   ├── db/                     # DB session & initial seed data
│   │   ├── models/                 # SQLAlchemy database models
│   │   ├── schemas/                # Pydantic v2 validation schemas
│   │   └── services/               # Business logic & services
│   ├── alembic/                    # Database migrations
│   ├── Dockerfile
│   └── requirements.txt
│
├── storefront/                     # 🛍️ Modern Next.js 16 Customer Storefront
│   ├── src/app/                    # Next.js App Router (shop, cart, checkout)
│   ├── src/components/             # Modern UI design system & layout components
│   └── package.json
│
├── management/                     # 📊 Next.js 16 Admin & Seller Portal
│   ├── src/app/                    # Admin dashboard, seller center & POS
│   ├── src/components/             # Management components & data tables
│   └── package.json
│
├── mobile-app/                     # 📱 Flutter Mobile Application
│   ├── lib/
│   │   ├── core/                   # Theme, constants, network & utilities
│   │   ├── features/               # Feature-first modules (auth, home, product, cart)
│   │   └── main.dart               # App entrypoint
│   ├── test/                       # Unit & Widget tests
│   └── pubspec.yaml
│
├── deploy/                         # 🚀 Production deployment configs & scripts
│   ├── production/                 # Docker Compose prod configuration
│   └── scripts/                    # Backup, restore & migration automation
│
├── web-app/                        # 🏛️ Monolithic web app (legacy reference)
├── pgadmin/                        # pgAdmin auto-server provisioning
│   └── servers.json
├── docker-compose.yml              # Multi-service development docker orchestration
├── run.sh                          # One-click startup script
├── PROJECT_CONTEXT.md              # Verified ground-truth audit & architecture guide
├── AGENTS.md                       # AI agent instructions & codebase conventions
└── README.md                       # Project documentation entry point
```

---

## 📖 API Documentation

Once the backend is running, visit:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc UI**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Key Endpoints Overview

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/auth/register` | Register new account | No |
| `POST` | `/api/auth/login` | Authenticate & get JWT | No |
| `GET` | `/api/auth/me` | Fetch active user profile | Yes |
| `GET` | `/api/products` | Paginated product listing | No |
| `GET` | `/api/products/{id}` | Get product details | No |
| `POST` | `/api/products` | Create product (admin) | Yes (Admin) |
| `GET` | `/api/categories` | List categories | No |
| `GET` | `/api/cart` | Get current user's cart | Yes |
| `POST` | `/api/cart/items` | Add product to cart | Yes |
| `POST` | `/api/orders` | Place a new order | Yes |
| `GET` | `/api/orders` | List user/admin orders | Yes |
| `GET` | `/api/notifications` | User notification list | Yes |
| `GET` | `/api/analytics/overview` | Admin KPI summary | Yes (Admin) |
| `POST` | `/api/pos/checkout` | Process POS in-store sale | Yes (Staff/Admin) |
| `GET` | `/api/pos/summary` | Today's POS register metrics | Yes (Staff/Admin) |
| `GET` | `/api/pos/customers` | Lookup loyalty customers | Yes (Staff/Admin) |

---

## 💻 Manual Setup (Without Docker)

<details>
<summary><b>Click to expand manual setup instructions</b></summary>

### 1. Database (PostgreSQL)
Ensure PostgreSQL 16 is installed and running locally:
```sql
CREATE DATABASE ecommerce_db;
CREATE USER ecommerce_user WITH PASSWORD 'GoPassword_123!';
GRANT ALL PRIVILEGES ON DATABASE ecommerce_db TO ecommerce_user;
```

### 2. Backend (FastAPI)
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run migrations and seed data
python -c "from app.db.database import init_db; from app.db.seed_data import seed_database; init_db(); seed_database()"

# Start API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Web Dashboard (Next.js)
```bash
cd web-app
npm install
npm run dev
```

</details>

---

## 🧪 Testing

### Backend Unit & Integration Tests
```bash
cd backend
pytest
```

### Mobile App Tests (110+ passing unit & widget tests)
```bash
cd mobile-app
flutter test
```

### Flutter Static Analysis
```bash
cd mobile-app
dart analyze lib/
```

---

## 🤝 Contributing

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

