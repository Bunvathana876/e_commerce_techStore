import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { summarizeAnalyticsPeriod } from "../analytics-utils.ts";

function buildSellerOrdersQuery(params) {
  const query = new URLSearchParams();
  if (params.page) query.append("page", String(params.page));
  if (params.limit) query.append("limit", String(params.limit));
  if (params.status && params.status !== "all") query.append("status", params.status);
  if (params.search && params.search.trim()) query.append("search", params.search.trim());
  const qs = query.toString();
  return `/seller/orders${qs ? `?${qs}` : ""}`;
}

function validateStoreSettingsDraft(draft) {
  if (!draft.store_name || !draft.store_name.trim()) {
    throw new Error("Store name is required.");
  }
  if (!draft.enable_card_payment && !draft.enable_cod_payment) {
    throw new Error("At least one payment method must remain enabled.");
  }
  if (draft.free_shipping_min < 0 || draft.standard_shipping_fee < 0 || draft.express_shipping_fee < 0) {
    throw new Error("Shipping amounts must be non-negative.");
  }
  return true;
}

describe("Seller Orders Query & Store Settings Validation", () => {
  it("serializes seller order query filters cleanly", () => {
    assert.equal(buildSellerOrdersQuery({ page: 1, limit: 10, status: "all", search: "" }), "/seller/orders?page=1&limit=10");
    assert.equal(
      buildSellerOrdersQuery({ page: 2, limit: 10, status: "shipped", search: "  #104 " }),
      "/seller/orders?page=2&limit=10&status=shipped&search=%23104"
    );
  });

  it("enforces at least one enabled payment method and valid shipping thresholds", () => {
    assert.throws(
      () =>
        validateStoreSettingsDraft({
          store_name: "Blue Panda",
          enable_card_payment: false,
          enable_cod_payment: false,
          free_shipping_min: 100,
          standard_shipping_fee: 2,
          express_shipping_fee: 12,
        }),
      /At least one payment method/
    );

    assert.equal(
      validateStoreSettingsDraft({
        store_name: "Blue Panda",
        enable_card_payment: true,
        enable_cod_payment: true,
        free_shipping_min: 100,
        standard_shipping_fee: 2,
        express_shipping_fee: 12,
      }),
      true
    );
  });
});

describe("Analytics Date Filtering & Top Product Summary", () => {
  const now = new Date("2026-11-23T12:00:00Z").getTime();
  const sampleOrders = [
    {
      id: 1,
      status: "delivered",
      total: 120,
      created_at: "2026-11-21T10:00:00Z",
      items: [{ product_id: 10, product_name: "USB-C Hub", quantity: 2, subtotal: 120 }],
    },
    {
      id: 2,
      status: "cancelled",
      total: 500,
      created_at: "2026-11-22T10:00:00Z",
      items: [{ product_id: 11, product_name: "Cancelled Monitor", quantity: 1, subtotal: 500 }],
    },
    {
      id: 3,
      status: "processing",
      total: 80,
      created_at: "2026-11-01T10:00:00Z",
      items: [{ product_id: 10, product_name: "USB-C Hub", quantity: 1, subtotal: 80 }],
    },
  ];

  it("scopes KPIs to selected window and excludes cancelled orders from revenue", () => {
    const sevenDays = summarizeAnalyticsPeriod(sampleOrders, "7days", now);
    assert.equal(sevenDays.totalOrders, 2);
    assert.equal(sevenDays.cancelledCount, 1);
    assert.equal(sevenDays.grossRevenue, 120);
    assert.equal(sevenDays.avgOrderValue, 120);
    assert.equal(sevenDays.topProducts.length, 1);
    assert.equal(sevenDays.topProducts[0].productName, "USB-C Hub");
    assert.equal(sevenDays.topProducts[0].unitsSold, 2);

    const thirtyDays = summarizeAnalyticsPeriod(sampleOrders, "30days", now);
    assert.equal(thirtyDays.totalOrders, 3);
    assert.equal(thirtyDays.grossRevenue, 200);
    assert.equal(thirtyDays.avgOrderValue, 100);
    assert.equal(thirtyDays.topProducts[0].unitsSold, 3);
  });
});
