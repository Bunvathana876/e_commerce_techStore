import test from "node:test";
import assert from "node:assert/strict";
import robots from "../../app/robots";
import sitemap from "../../app/sitemap";

test("SEO & Search Engine Directives Suite", async (t) => {
  await t.test("robots() disallows private authenticated routes and allows public catalog", () => {
    const config = robots();
    assert.ok(config.sitemap, "Sitemap URL must be defined");
    assert.ok(
      typeof config.sitemap === "string" && config.sitemap.includes("/sitemap.xml"),
      "Sitemap must point to sitemap.xml"
    );

    const rules = Array.isArray(config.rules) ? config.rules[0] : config.rules;
    assert.ok(rules, "Robots rules must exist");

    const disallowRaw = Array.isArray(rules.disallow) ? rules.disallow : [rules.disallow];
    const allowRaw = Array.isArray(rules.allow) ? rules.allow : [rules.allow];

    const disallow = disallowRaw.filter((p): p is string => typeof p === "string");
    const allow = allowRaw.filter((p): p is string => typeof p === "string");

    // Check disallowed sensitive routes
    assert.ok(disallow.some((p) => p.includes("/account")), "Disallow must include /account");
    assert.ok(disallow.some((p) => p.includes("/checkout")), "Disallow must include /checkout");
    assert.ok(disallow.some((p) => p.includes("/orders")), "Disallow must include /orders");
    assert.ok(disallow.some((p) => p.includes("/cart")), "Disallow must include /cart");
    assert.ok(disallow.some((p) => p.includes("/login")), "Disallow must include /login");

    // Check allowed public routes
    assert.ok(allow.some((p) => p === "/"), "Allow must include /");
    assert.ok(allow.some((p) => p === "/shop"), "Allow must include /shop");
    assert.ok(allow.some((p) => p === "/categories"), "Allow must include /categories");
    assert.ok(allow.some((p) => p === "/deals"), "Allow must include /deals");
  });

  await t.test("sitemap() outputs valid static routes and canonical URL structure", async () => {
    const entries = await sitemap();
    assert.ok(Array.isArray(entries), "Sitemap must return an array of entries");
    assert.ok(entries.length >= 6, "Sitemap must contain at least 6 core public routes");

    const urls = entries.map((e) => e.url);
    assert.ok(urls.some((u) => u.endsWith("/shop")), "Sitemap must contain /shop");
    assert.ok(urls.some((u) => u.endsWith("/categories")), "Sitemap must contain /categories");
    assert.ok(urls.some((u) => u.endsWith("/deals")), "Sitemap must contain /deals");
    assert.ok(urls.some((u) => u.endsWith("/new-arrivals")), "Sitemap must contain /new-arrivals");
    assert.ok(urls.some((u) => u.endsWith("/stores")), "Sitemap must contain /stores");

    for (const entry of entries) {
      assert.ok(entry.url.startsWith("http"), `URL ${entry.url} must start with http/https`);
      assert.ok(entry.lastModified instanceof Date, `Entry ${entry.url} must have a valid lastModified Date`);
    }
  });
});
