# Blue Panda Storefront UI/UX Redesign Plan

## First-run scope (November 1, 2026)

This first implementation is deliberately limited to the shared homepage presentation layer and homepage. The live catalog API, Zustand cart/wishlist actions, search dialog, authentication, checkout, shop page, and product-detail page remain unchanged.

Reference translation: use the Shopcart shot's compact shopping shell, spacious promotional composition, category-first discovery, and dense product collections. Blue Panda retains its own logo, blue palette, product imagery, and factual catalog data; no Shopcart assets, copy, green branding, ratings, discounts, or delivery claims are copied or invented.

Implementation order:

1. Establish the requested white/soft-gray/blue tokens and small reusable homepage primitives.
2. Refine the homepage into a single promotional hero, category cards, featured live products, rating-derived electronics, real sale products, and a factual shopping-utility strip.
3. Verify lint, type/build checks, existing tests, and responsive behavior at 375px, 768px, and 1440px.
4. Stop before catalog and product-detail redesign work.

> Audit date: 2026-11-01  
> Scope: the customer-facing Next.js application in `storefront/` only.  
> Method: static inspection of the current routes, shared components, styles, configuration, and storefront state/data callers. A live browser render was not available in the audit environment, so viewport and assistive-technology behavior must be verified during implementation.  
> Constraint: this is a design and implementation plan. No storefront source code, authentication, API integration, checkout/payment logic, or Zustand state was changed.

## 1. Executive Summary

The storefront already has a recognizable Blue Panda identity and broad shopping coverage. It uses a consistent font, familiar commerce patterns, responsive Tailwind layouts, useful empty states, native modal dialogs, visible focus styles, and reduced-motion support.

Its main design problem is not a lack of polish; it is an excess of competing polish. Nearly every surface uses large radii, badges, shadows, gradients, promotional copy, decorative effects, and multiple calls to action. Important shopping information therefore competes with marketing decoration. The result feels like a feature showcase rather than a calm, premium retail experience.

The highest-value redesign is to establish a small semantic design system, simplify the shared product card, and then rebuild the homepage and catalog around those foundations. This will improve the largest number of routes without changing business logic.

## 2. Verified Storefront Structure

- Framework: Next.js 16 App Router, React 19, strict TypeScript, and Tailwind CSS 4.
- State: persisted Zustand commerce state in `storefront/src/lib/store.ts`.
- Customer routes: `storefront/src/app/(store)/`.
- Authentication routes: `storefront/src/app/(auth)/`.
- Shared storefront UI: `storefront/src/components/store/`.
- Global visual rules: `storefront/src/app/globals.css`.
- Shared store shell: `storefront/src/app/(store)/layout.tsx`.
- Font: Plus Jakarta Sans through the root layout.

The store layout mounts the navbar, footer, cart drawer, quick-view dialog, search dialog, and toast viewport on every customer route. Most route pages are client components and fetch their data after hydration.

## 3. Current Strengths to Preserve

- The blue, white, slate, and soft-gray palette is appropriate for the brand.
- Plus Jakarta Sans gives the store a modern and readable base.
- Major shopping flows are discoverable: search, wishlist, cart, checkout, account, and orders.
- The responsive grid system generally collapses safely on small screens.
- Product cards expose price, sale state, rating, stock, wishlist, and add-to-cart actions.
- The shop has search, filters, sorting, empty results, and grid/list views.
- The cart and checkout have clear totals and primary actions.
- Native `<dialog>` is used for search and quick view, including light-dismiss handling.
- Global `:focus-visible` and `prefers-reduced-motion` rules are present.
- Several icon-only actions already have accessible names.
- Loading, empty, and error states exist in important purchase flows, although they are not yet consistent across all routes.

## 4. Current UI Problems

### Priority A — Shopping clarity and trust

1. **The homepage is too long and promotional.** It contains eight major sections: an auto-advancing hero, trust pillars, category showcase, featured deals, tabbed collections, voucher vault, official stores, and a mobile-app banner. Several sections repeat the same shipping, authenticity, discount, and synchronization messages.
2. **Unsupported or unverified promises are presented as normal store guarantees.** Examples include 30-day free returns, one-year warranty, authenticity guarantees, same-day dispatch, live tracking, concierge support, and synchronized experiences. These appear in the hero, product detail, cards, cart, footer, and other promotional surfaces.
3. **Showcase fixtures are displayed as ordinary catalog content.** Homepage, shop, categories, deals, stores, product detail, and search initialize with `SHOWCASE_*` records and later fetch live data. This can make demo content appear to be real inventory and causes content replacement after hydration.
4. **A visible product-card defect duplicates every grid product name.** `ProductCard.tsx` renders `{product.name}` twice in the grid-card link. This harms scanability and makes every card look unfinished.
5. **Too many actions compete at once.** Product cards can show wishlist, quick view, add, product link, seller link, rating, category, discount, “Top Pick,” stock, and pricing in one compact surface. Product detail similarly gives “Add to Bag” and “Express Buy Now” nearly equal prominence.

### Priority B — Visual hierarchy and consistency

1. **The interface overuses rounded containers.** `rounded-3xl`, custom 2rem radii, pills, and circular controls appear on almost every section and nested card. There is little distinction between primary surfaces, secondary panels, and small controls.
2. **Gradients and blur effects are too frequent.** The body has two radial gradients; the hero uses a dark multi-color gradient and glow orbs; auth uses a sliding gradient panel; dialogs and actions repeatedly use backdrop blur. These conflict with the requested clean, minimal direction.
3. **Shadows are inconsistent and often decorative.** Cards range from `shadow-xs` to large colored shadows. Hovering frequently changes border, shadow, scale, and color simultaneously.
4. **Typography is dense at the small end.** Many labels use 10–11px text, uppercase tracking, and extra-bold weights. This makes metadata harder to read and creates a “dashboard” tone instead of a premium retail tone.
5. **The current design-token layer is too small.** `globals.css` defines only page background, ink, and brand variables. Success, warning, error, muted text, border, surface, radii, shadows, and motion are repeatedly expressed as utility combinations.
6. **Page headers are not visually unified.** Shop uses a large dark promotional header, categories uses a simpler white heading, and cart/checkout use another pattern. The visual importance of a page title changes by route.

### Priority C — Navigation and search

1. **The header has too many layers and destinations.** A promotional bar sits above a sticky navigation row, with store links, search, notification controls, account actions, wishlist, cart, and staff routing competing for attention.
2. **The navbar includes commerce promotion inside navigation.** Coupon copy actions and return/shipping claims make the header busier and increase its height.
3. **Desktop search is a launcher rather than a strong always-visible shopping tool.** Search is important enough to deserve a prominent field at desktop widths instead of looking like one of many icon actions.
4. **Mobile navigation expands inline below the header.** This pushes page content, exposes many secondary links, and lacks the clearer hierarchy of a focused mobile sheet/drawer.
5. **Dropdown controls need a complete accessibility pass.** The inspected navbar controls do not consistently expose expanded state, controlled element IDs, or current-page state.

### Priority D — Mobile usability

1. **The hero is still content-heavy on narrow screens.** Large headings, body copy, multiple CTAs, trust items, carousel controls, imagery, and floating product information compete above the fold.
2. **The shop filter panel opens inline.** On mobile this lengthens and shifts the page rather than providing a contained filter sheet with an obvious result count and apply action.
3. **Product cards are one per row on the smallest breakpoint.** The large square image and generous content make catalog scanning slow. A carefully reduced two-column variant can work on phones wide enough to support it, while very narrow devices can remain one-column.
4. **Cart item rows become vertically tall.** Image, details, quantity, price, and remove actions split into stacked regions, causing excessive scrolling for multi-item carts.
5. **Checkout is long and cognitively heavy.** Customer details, delivery, payment, order review, notices, and summary all need a clearer step hierarchy and a compact mobile summary.
6. **Product purchase actions are not persistently reachable.** On a long product page, mobile users must scroll back to the buy box. A compact bottom purchase bar would reduce friction, subject to preserving the existing add/buy behavior.
7. **Several icon buttons use 32–40px visual boxes.** Touch targets should consistently reach at least 44px without making the icon itself oversized.

### Priority E — Accessibility

1. **Authentication inputs rely on placeholders instead of persistent labels.** This reduces clarity after typing and weakens screen-reader/form usability.
2. **Product-detail tabs are visually styled buttons without tab semantics.** They need `tablist`, `tab`, `tabpanel`, selected state, keyboard behavior, and focus management if they remain tabs.
3. **The clickable product image is a non-semantic zoom control.** A clickable `div` does not provide keyboard activation or an accessible control name.
4. **The hero carousel needs pause and announcement behavior.** It auto-advances every 6.5 seconds but does not visibly expose pause behavior or a clearly defined accessible carousel structure.
5. **Some status information is color-led and visually small.** Stock, discount, success, warning, and ratings should keep text/icons and meet contrast requirements.
6. **Repeated 10–11px labels should be raised to a practical minimum.** Essential information should generally use at least 12–14px depending on weight and context.
7. **Card article headings should be semantic.** Product names should be headings within product-card articles, not only styled links.
8. **Filters need stronger field names and grouping.** Use visible labels, fieldsets/legends where suitable, keyboard-friendly controls, and a live result summary.

### Priority F — UI-related performance

1. **Most storefront pages are client-rendered.** The homepage, shop, categories, product detail, cart, checkout, account, orders, deals, stores, and wishlist use client components. This increases shipped JavaScript and delays meaningful catalog content.
2. **Raw `<img>` is used throughout the storefront.** The audited TSX contains many raw image elements, including hero, category, card, cart, and dialog imagery. This misses Next.js image optimization, responsive sizing, and consistent loading behavior.
3. **Remote images are unrestricted.** `next.config.ts` accepts arbitrary HTTP and HTTPS image hosts. A later image migration should allow only trusted backend/media hosts.
4. **The hero keeps multiple large slide images in the DOM.** Hidden slides still add markup and can add image/network pressure.
5. **Catalog filtering happens over a large client-side collection.** Sorting, searching, seller, category, rating, price, and stock filtering all run in the browser. The UI redesign should not worsen this with heavier card effects or additional derived lists.
6. **All global overlays are mounted for every store route.** Search and quick view can be lazily loaded or split into smaller client islands while preserving their behavior.
7. **Large components increase hydration and maintenance cost.** The homepage, product detail, checkout, navbar, and shop page each combine data loading, state, transformations, and extensive markup.
8. **Storefront CSS still includes POS print rules.** They do not belong to the customer storefront after frontend separation and add obsolete global behavior. Removal should be verified separately because this audit does not modify code.

## 5. Proposed Design System

The redesign should use semantic roles rather than inventing a new color for each component.

### Color roles

| Token | Suggested value | Use |
|---|---:|---|
| `canvas` | `#F8FAFC` | Page background |
| `surface` | `#FFFFFF` | Cards, forms, header |
| `surface-subtle` | `#F1F5F9` | Secondary panels and controls |
| `text-strong` | `#0F172A` | Headings and prices |
| `text` | `#334155` | Body copy |
| `text-muted` | `#64748B` | Secondary metadata |
| `border` | `#E2E8F0` | Default dividers and outlines |
| `brand` | `#2563EB` | Primary actions and links |
| `brand-hover` | `#1D4ED8` | Primary hover/pressed state |
| `brand-soft` | `#EFF6FF` | Selected and informational backgrounds |
| `success` | `#047857` | In-stock and confirmed states |
| `warning` | `#B45309` | Low stock and pending states |
| `danger` | `#BE123C` | Destructive and error states |

All text/background pairs must be checked against WCAG AA. Lighter colors should be accents or backgrounds, not normal text on white.

### Typography

- Keep Plus Jakarta Sans.
- Use one clear display style, three heading sizes, and two body sizes.
- Suggested scale: 48/56 hero desktop, 36/44 hero mobile, 32/40 page title, 24/32 section title, 18/28 card/detail heading, 16/26 body, 14/22 secondary body, and 12/18 metadata.
- Use `700` for main headings/prices and `600` for controls. Reserve `800` for rare emphasis.
- Avoid all-uppercase copy except very short state labels.
- Use tighter line length for marketing copy and comfortable line height for product information.

### Spacing and layout

- Base spacing: 4, 8, 12, 16, 24, 32, 48, 64, and 96px.
- Page container: current `max-w-7xl` is appropriate; standardize horizontal padding at 16px mobile, 24px tablet, and 32px desktop.
- Section rhythm: 48–64px mobile and 72–96px desktop.
- Card padding: 16px compact, 24px standard, 32px for large information panels.
- Prefer whitespace and dividers over nested cards.

### Shape, borders, and elevation

- Controls: 8–12px radius.
- Product and content cards: 12–16px radius.
- Large editorial panels/dialogs: 20–24px radius.
- Avoid pill shapes unless the content is a badge, segmented control, or compact filter.
- Default cards should use a 1px border and little or no shadow.
- Use one subtle elevation for floating navigation/dialogs and one stronger elevation for modals only.

### Motion

- Standard interaction: 150ms; panel/dialog transition: 200–240ms.
- Animate opacity and small translations only.
- Limit image hover scale to approximately 1.02–1.03.
- Do not auto-animate decorative elements.
- Preserve the existing reduced-motion rule and ensure carousels stop auto-advancing for reduced motion.

### Core component states

Every reusable control must define default, hover, focus-visible, active, disabled, loading, error, and success behavior. Every data view must define loading, empty, failure, retry, and populated states.

## 6. Screen-by-Screen Improvements

### Homepage

Recommended order:

1. One restrained hero with one primary CTA and one secondary text link.
2. A compact category row/grid.
3. One featured-product collection using the shared card.
4. One clearly labeled promotion or deal panel.
5. Official stores only if real seller data is available.
6. A compact factual service strip and simplified footer.

Remove or merge the duplicate trust pillars, voucher vault, repeated deal messaging, and mobile-app ecosystem banner. If the carousel remains, show one image at a time, provide pause/previous/next controls, and use concise slide copy. Prefer a static editorial hero for faster loading and clearer focus.

### Navbar and search

- Remove promotional coupon interaction from the main navigation.
- Keep at most one slim announcement line on desktop; hide or shorten it on mobile.
- Use three desktop zones: brand, prominent search field, and account/wishlist/cart actions.
- Keep primary navigation to Shop, Categories, Deals, and Stores, with clear current-page state.
- Replace the inline mobile menu with an accessible sheet containing primary links first and account/order links second.
- Retain the search dialog for suggestions/results, but launch it from a visually prominent field.
- Add `aria-expanded`, `aria-controls`, current-page semantics, Escape handling, and focus return for menus.

### Hero/banner

- Replace glow orbs, glass panels, floating product pills, and multiple trust claims with one strong image and concise copy.
- Keep the heading to roughly two lines and body copy to two short lines.
- Use one brand-blue primary button and one quiet secondary link.
- Use real, high-quality imagery with responsive crops and stable aspect ratios.
- Avoid placing essential copy over detailed imagery without a solid contrast treatment.

### Product cards

- Fix the duplicated product name first.
- Define two deliberate variants: `grid` for discovery and `list` for comparison/search.
- Grid hierarchy: image, optional single sale badge, product name, seller or category, rating, current/original price, and one add action.
- Remove descriptions and “Top Pick” from grid cards.
- Show at most one inventory message, only when low/out of stock.
- Keep wishlist in the image corner; make quick view a desktop enhancement rather than an equal primary action.
- Use a consistent 4:5 or square image ratio based on available catalog media.
- Keep action targets at least 44px and make the full title/image navigation obvious.
- Add semantic headings and avoid hiding required actions behind hover on touch devices.

### Product listing and filters

- Replace the large dark catalog banner with a clean page heading and a compact search/results toolbar.
- Keep desktop filters in a calm sticky sidebar with clear groups and reset behavior.
- Use a bottom sheet or full-height drawer for mobile filters; show active-filter count and “Show N products.”
- Render selected filters as removable chips above results.
- Preserve grid/list choice only if analytics or user feedback justify both; otherwise simplify to one excellent grid.
- Add skeletons and an explicit failure/retry state instead of immediately showing fixtures as normal products.
- Keep filters and sort reflected in the URL where current behavior supports it, so results remain shareable and navigable.

### Product details

- Use a real gallery region with a stable main image and thumbnails when multiple images exist; otherwise do not imply a gallery.
- Replace the clickable zoom `div` with a semantic button or dedicated zoom dialog.
- Make the desktop buy panel sticky within the product introduction.
- On mobile, add a compact bottom bar with price and the existing primary purchase action after careful overlap/safe-area testing.
- Reduce the purchase area to one dominant action; treat buy-now as secondary if it must remain.
- Show only verified delivery, warranty, return, and seller information.
- Replace decorative marketing cards in Overview with actual description and specifications.
- Implement proper tabs or replace them with stacked sections/accordions on mobile.
- Separate rating summary, review list, and review form; show a meaningful empty state when no approved reviews exist.

### Categories and stores

- Replace tall, dark image-overlay category cards with lighter cards using a clean image, category name, and product count.
- Use two columns on normal phones, three on tablet, and four on desktop when content length allows.
- Keep descriptions short or omit them from overview cards.
- Use one consistent store-card pattern: logo/cover, verified name, product count, rating only when meaningful, and one “View store” link.

### Cart and cart drawer

- Give the cart drawer one job: confirm additions and enable a fast path to bag/checkout.
- Keep detailed quantity editing, coupon entry, and totals on the full cart page.
- Reduce duplicated shipping-meter and promotional content.
- Make mobile cart rows compact: thumbnail left, product/variant center, price/remove aligned, and quantity below without full-width stacking.
- Add confirmation before clearing the entire bag.
- Make the order summary visually quiet and keep total plus checkout CTA dominant.
- Replace marketing-style security text with concise, accurate transaction information.

### Checkout

- Use a clear sequence: Contact, Delivery, Payment, Review.
- Keep a two-column desktop layout with a sticky order summary; collapse the summary into an accessible disclosure near the top on mobile.
- Use persistent labels, short help text, correct autocomplete attributes, and inline field-level errors.
- Visually disable or hide payment methods that are not actually available; do not style simulations as live providers.
- Keep notices close to the field or action they explain.
- Simplify the confirmation page to order number, factual status, delivery address, total, and two next actions.
- Preserve all existing checkout validation and server-confirmation behavior during visual refactoring.

### Login and register

- Replace the animated two-panel auth card with one focused white card.
- Keep the Blue Panda logo, title, short context, form, submit button, and one login/register switch link.
- Add visible labels for every field; placeholders may provide examples only.
- Remove the large sliding gradient panel and long promotional copy.
- Treat demo-account shortcuts as development-only UI and clearly label them when enabled.
- Keep error messages in a live region and associate field errors with their inputs.
- Add show/hide password controls with accessible names if implemented.

### Footer

- Remove repeated trust/benefit cards and unsupported promises.
- Keep brand summary, Shop, Help, Account, legal links, and verified contact information.
- Do not display newsletter success unless an actual subscription succeeds.
- Reduce the number of columns and collapse secondary groups on mobile.

## 7. Components to Reuse

Reuse these behaviors and refactor their presentation rather than replacing their contracts:

- `ProductCard` grid/list public API and Zustand actions.
- `StoreNavbar` authentication, counts, notifications, and store synchronization behavior.
- `CartDrawer` Zustand interactions and cart totals.
- `SearchCommandDialog` search state, native dialog behavior, and keyboard shortcut.
- `QuickViewDialog` native dialog behavior and commerce actions.
- `ToastViewport` live-region behavior.
- Existing store layout and route groups.
- Existing API types, store-catalog helpers, checkout security helpers, and Zustand store.

## 8. Components to Simplify or Extract

Recommended UI-only primitives:

- `Button` with primary, secondary, quiet, danger, loading, and icon variants.
- `IconButton` with enforced accessible name and touch target.
- `Field`, `SelectField`, and inline `FieldError`.
- `Badge` limited to sale, stock, and status roles.
- `SectionHeader` with optional single link/action.
- `PriceDisplay` for current price, original price, and savings.
- `ProductImage` wrapper for aspect ratio, fallback, sizes, and eventual Next Image adoption.
- `QuantityStepper` shared by product detail, cart, drawer, and quick view.
- `EmptyState`, `ErrorState`, and product-card skeletons.
- `FilterGroup`, active filter chips, and a mobile `FilterSheet`.
- `StoreCard`, `CategoryCard`, and factual `ServiceStrip`.

Simplify or split these large files without changing their data contracts:

- Homepage into hero, categories, featured products, promotion, and stores sections.
- Navbar into announcement, desktop nav, action group, and mobile sheet.
- Product detail into gallery, buy box, product information, reviews, and related products.
- Checkout into contact, delivery, payment, summary, and confirmation sections.
- Auth form into shared field primitives and one focused mode-specific form.

## 9. Step-by-Step Implementation Roadmap

### Phase 0 — Baseline and safeguards

1. Capture screenshots at 320, 375, 768, 1024, and 1440px for all core routes.
2. Record Lighthouse mobile/desktop results for home, shop, and one product.
3. Keyboard-test navbar, search, quick view, filters, cart drawer, auth, and checkout.
4. Add a visual checklist for live, loading, empty, error, out-of-stock, signed-in, and signed-out states.
5. Confirm which delivery, returns, warranty, seller, and payment claims are actually supported before rewriting copy.

### Phase 1 — Foundations and shared product card

1. Add semantic color, spacing, radius, elevation, typography, and motion tokens to `globals.css`.
2. Introduce the minimal shared primitives listed above without adding a package.
3. Fix the duplicate product name and redesign `ProductCard` grid/list variants.
4. Migrate one homepage product collection as the reference implementation.
5. Verify card behavior in home, shop, deals, wishlist, related products, search, and quick view.

### Phase 2 — Navigation, search, and shell

1. Simplify the announcement and desktop header.
2. Make search visually prominent.
3. Replace the inline mobile navigation with an accessible sheet.
4. Simplify the footer and remove obsolete storefront POS print styles after verification.
5. Preserve all auth/session/count/notification behavior.

### Phase 3 — Homepage

1. Replace the current hero with the restrained editorial pattern.
2. Reduce the homepage to the recommended section order.
3. Consolidate repeated trust and promotional content.
4. Add explicit loading/error/demo presentation without changing API integration in the visual task.
5. Test the page at every baseline viewport and with reduced motion.

### Phase 4 — Catalog, categories, deals, and stores

1. Standardize page headings and result toolbars.
2. Implement desktop filter groups and the mobile filter sheet.
3. Add selected filter chips and clearer result feedback.
4. Redesign category and store cards.
5. Confirm grid density and card image crops across real catalog data.

### Phase 5 — Product details and overlays

1. Refactor the product introduction into gallery and sticky buy panel.
2. Simplify claims, actions, specifications, and reviews.
3. Add semantic tabs or mobile accordions.
4. Align quick view with the new product card and buy-box patterns.
5. Add the mobile purchase bar only after overlap, keyboard, and safe-area tests.

### Phase 6 — Cart, checkout, and authentication

1. Separate the cart drawer’s quick-confirmation role from the full cart page.
2. Compact mobile cart rows and simplify the summary.
3. Reorganize checkout visually while preserving validation, totals, API calls, and server-confirmed status.
4. Replace the sliding auth presentation with focused forms and persistent labels.
5. Test success and every failure path, not only the happy path.

### Phase 7 — Performance and accessibility pass

1. Move suitable route shells and catalog content toward server components, leaving Zustand and interactive controls as client islands.
2. Adopt `next/image` with correct `sizes`, explicit geometry, and trusted remote hosts.
3. Lazy-load heavy global overlays where safe.
4. Run automated and manual accessibility checks.
5. Compare Lighthouse and bundle results with Phase 0; accept changes only when interaction and visual quality do not regress performance.

## 10. Verification for Every Implementation Phase

- Run `rtk npm run lint`, `rtk npm test`, and `rtk npm run build` from `storefront/`.
- Inspect `rtk git diff --check`, `rtk git diff`, and `rtk git status --short`.
- Test keyboard navigation, focus order, Escape/close behavior, and focus return.
- Test 200% browser zoom, reduced motion, and text resizing.
- Check at least 320, 375, 768, 1024, and 1440px widths.
- Check loading, empty, error, retry, offline, disabled, out-of-stock, success, signed-in, and signed-out states.
- Confirm product, price, stock, coupon, shipping, total, payment, and order status remain sourced from the existing logic.
- Verify the cart, wishlist, quick view, search, login redirect, checkout, and order confirmation still behave exactly as before unless a separately approved task changes them.

## 11. Recommended First Task

Start with a **design-foundation and product-card vertical slice**:

1. Add semantic tokens in `storefront/src/app/globals.css`.
2. Create only the small primitives required by the card: product image, price display, badge, and icon button.
3. Fix and simplify `storefront/src/components/store/ProductCard.tsx` without changing its props or Zustand actions.
4. Apply the new card to one featured-products section on the homepage.
5. Verify it in grid/list layouts, at phone and desktop widths, with sale, regular, low-stock, and out-of-stock products.

This is the best first task because the card is the storefront’s most repeated shopping surface. It establishes the visual language, fixes a visible defect, and provides a reusable reference before the larger homepage, catalog, and product-detail redesigns begin.

## 12. Explicitly Out of Scope for This Redesign

- Changes to `management/`, `backend/`, `mobile-app/`, or the legacy `web-app/`.
- Authentication/session behavior.
- API endpoints, response contracts, or integration strategy.
- Checkout totals, validation, order creation, or payment handling.
- Zustand store shape, persistence, or synchronization logic.
- Adding UI packages or animation libraries.
- Treating demo fixtures, simulated providers, or unsupported guarantees as production features.

Any functional work needed to resolve showcase-data behavior, unsupported claims, remote image policy, or server/client rendering should be proposed as a separate, explicitly approved task before implementation.
