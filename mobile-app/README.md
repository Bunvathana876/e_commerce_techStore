# 🐼 Blue Panda — E-Commerce Mobile App

A clean, modern E-Commerce mobile application built with **Flutter** and **Dart**, using **Provider** for state management. It connects to the project's **FastAPI** backend (`../backend`) for live products, categories, reviews, orders, and notifications.

The app is built around a feature-first architecture, minimal UI, smooth page transitions, and real-world loading and offline behavior.

---

## ✨ Features

### 🔐 Authentication & Onboarding
- Welcome, Login, and Sign Up screens with real-time form validation.
- Login and registration through the backend (`/api/v1/auth`).
- **Persistent sessions**: the token and user are saved with `SharedPreferences`, so you stay signed in after restarting the app.
- Light and dark theme support on the auth screens.

### 🏠 Home & Discovery
- Promotional banner carousel with page indicators and auto-scroll.
- Horizontal category bar for quick filtering.
- A minimal 2-column product grid. Cards show the image, name, short description, price, discount, and rating. To add an item to the cart, open its detail page.
- Real-time search, plus sort and filter options (price low→high, high→low, rating).
- Lazy loading: more products load as you scroll down.
- Pull to refresh reloads data from the backend.

### 🗂️ Categories
- Department grid with images and item counts, loaded from the backend.
- A dedicated product list for each category, with its own search.
- Shimmer skeletons appear while categories load.

### 📦 Product Details
- Hero image transitions, variant selection, and a quantity selector with live price updates.
- **Interactive rating breakdown** (5★ → 1★ bars with percentages). Tap a star row to filter reviews by that rating.
- Customer reviews from the backend, plus a bottom sheet for writing a review.

### 🛒 Cart, Checkout & Orders
- Cart with quantity steppers, item removal, free-shipping progress, and an order summary.
- Promo codes (e.g. `WELCOME10`), validated by the backend with local verification as a fallback.
- Checkout with address and payment method selection, followed by an order success screen.
- Order history, order details, and order status tracking.

### 🔔 Notifications
- Notifications list with category and unread filters.
- Mark as read, mark all as read, delete, and **Clear All**. Cleared and deleted items stay removed after restarting the app.

### ❤️ Wishlist & 👤 Profile
- Wishlist screen. Favorites sync to the backend when you're signed in.
- Profile with account stats, order shortcuts, notification count, settings, and a persistent light/dark theme toggle.

---

## 🌐 Backend Connection & Offline Behavior

The app shows **only real data from the backend**. When the API is unreachable, it never falls back to fake or sample data.

| Situation | What the user sees |
|---|---|
| Fetching data | Animated **shimmer skeletons** for products and categories, like production shopping apps |
| Backend online | Live products, categories, and reviews from the database |
| Backend offline / no network | A **"Network is not connected"** screen with a **Retry Connection** button. No fake products, categories, reviews, or notifications are shown |
| Backend comes back online | Tap **Retry Connection** or pull to refresh to load live data |

### Default API base URL
Configured in [`lib/core/constants/api_endpoints.dart`](lib/core/constants/api_endpoints.dart):

| Platform | Base URL |
|---|---|
| Android emulator | `http://10.0.2.2:8000` |
| iOS simulator / macOS / Web | `http://localhost:8000` |

To use a **real device** on the same Wi-Fi network, or any other server, pass your computer's LAN IP:

```bash
flutter run --dart-define=API_URL=http://192.168.1.10:8000
```

---

## 🏗️ Project Architecture

```text
lib/
├── main.dart                 # App entry, MultiProvider setup
├── app/                      # MyApp, routes
├── core/
│   ├── constants/            # API endpoints & base URL config
│   ├── network/              # ApiClient, ApiResponse, typed exceptions
│   ├── theme/                # Light & dark themes
│   └── utils/                # Page transitions, validators, environment helpers
├── features/
│   ├── auth/                 # Welcome, Login, Sign Up, AuthProvider, services
│   ├── home/                 # Home dashboard (banners, categories, product grid)
│   ├── products/             # ProductProvider, product detail, cards, API service
│   ├── categories/           # Categories grid, category products, provider
│   ├── reviews/              # Rating breakdown, review cards, write-review sheet
│   ├── cart/                 # Cart screen, CartProvider, promo codes
│   ├── checkout/             # Checkout flow & order success
│   ├── orders/               # Order history, details, tracking
│   ├── notifications/        # Notifications screen, provider, clear-all
│   ├── favorites/            # Wishlist screen
│   ├── navigation/           # Bottom navigation shell
│   └── profile/              # Profile & settings (theme provider)
└── shared/
    └── widgets/              # BouncingButton, promo carousel, bottom nav, etc.
```

---

## 🛠️ Tech Stack

| Package | Purpose |
|---|---|
| [`provider`](https://pub.dev/packages/provider) | State management (`ChangeNotifier`) |
| [`http`](https://pub.dev/packages/http) | REST API calls to the FastAPI backend |
| [`shared_preferences`](https://pub.dev/packages/shared_preferences) | Session, theme, and notification persistence |
| [`shimmer`](https://pub.dev/packages/shimmer) | Skeleton loading placeholders |
| [`flutter_animate`](https://pub.dev/packages/flutter_animate) | UI animations |
| [`smooth_page_indicator`](https://pub.dev/packages/smooth_page_indicator) | Banner carousel indicators |
| [`google_fonts`](https://pub.dev/packages/google_fonts) | Typography |
| [`flutter_launcher_icons`](https://pub.dev/packages/flutter_launcher_icons) | App icon generation (dev) |

- **Flutter SDK**: Dart `^3.11.1`
- **Design**: Material 3 with custom light and dark themes

---

## 🚀 Getting Started

### Prerequisites
- [Flutter SDK](https://docs.flutter.dev/get-started/install) (Dart 3.11+)
- Android Studio, Xcode, or VS Code with the Flutter plugin
- Docker (to run the backend)

### 1. Start the backend
From the project root (`e-commerce/`):

```bash
./run.sh
# or
docker compose up --build -d
```

This starts PostgreSQL, pgAdmin, the FastAPI backend on `http://localhost:8000`, and the web app. You can check the backend at `http://localhost:8000/health` or in the API docs at `http://localhost:8000/docs`.

**Demo accounts** (seeded automatically):

| Role | Email | Password |
|---|---|---|
| Customer | `customer@ecommerce.com` | `password123` |
| Seller | `seller@ecommerce.com` | `seller123` |
| Admin | `admin@ecommerce.com` | `admin123` |

### 2. Run the mobile app

```bash
cd mobile-app
flutter pub get
flutter run
```

### 3. Analyze & test

```bash
flutter analyze
flutter test
```

---

## 🧪 Testing

The test suite lives in `test/` and covers unit tests and widget tests:

| Area | Tests |
|---|---|
| Core / Network | `api_network_test.dart`, `network_disconnected_test.dart` (no fake data when offline) |
| Utils | `page_transitions_test.dart`, `validators_test.dart` |
| Auth | Login/Sign Up redesign, theme mode, session persistence |
| Home & Products | Product cards, product detail, lazy loading, detail sync |
| Categories | Navigation, lazy loading |
| Reviews | Rating breakdown and review submission |
| Cart & Orders | Checkout, promo codes, order tracking, order history |
| Notifications | Filtering, mark as read, delete, clear all |
| Profile | Settings navigation, theme persistence |
| Shared widgets | Promo carousel, bottom navigation bar |

> **Note:** During `flutter test`, providers use built-in sample data so the tests can run without a live backend. This test-only data is never shown in the real app.

---

## 🩺 Troubleshooting

| Problem | Fix |
|---|---|
| "Network is not connected" while the backend is running | Check `http://localhost:8000/health`. On a real device, use `--dart-define=API_URL=http://<your-LAN-IP>:8000` |
| Android emulator can't connect | Make sure the backend is running on port `8000`. The emulator reaches your computer through `10.0.2.2` |
| Product images don't load | Images are served from the backend's `/uploads`. Make sure the backend is running and reachable |
| Old session after a database reset | Sign out from Profile and sign in again |

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
