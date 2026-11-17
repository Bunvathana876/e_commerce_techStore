import assert from "node:assert/strict";
import { test } from "node:test";
import type { ApiProduct } from "../api";
import { probeProductImage, selectHeroProductsWithImages } from "../hero-images";

function product(id: number, imageUrl: string | null): ApiProduct {
  return {
    id,
    category_id: 1,
    name: `Product ${id}`,
    price: 25,
    stock: 5,
    rating: 0,
    is_active: true,
    image_url: imageUrl,
  };
}

test("hero chooses real products with usable images after missing and broken URLs", async () => {
  const products = [
    product(1, null),
    product(2, "assets/images/products/missing.png"),
    product(3, "/uploads/products/portrait.png"),
    product(4, "/uploads/products/landscape.png"),
  ];
  const checked: string[] = [];
  const selected = await selectHeroProductsWithImages(products, async (url) => {
    checked.push(url);
    return !url.endsWith("missing.png");
  });

  assert.deepEqual(selected.map((item) => item.id), [3, 4]);
  assert.equal(checked.length, 3);
  assert.ok(checked.some((url) => url.endsWith("/uploads/products/portrait.png")));
});

test("hero keeps the backend order and stops after four valid photographs", async () => {
  const products = Array.from({ length: 8 }, (_, index) => product(index + 1, `/uploads/${index + 1}.png`));
  const checked: string[] = [];
  const selected = await selectHeroProductsWithImages(products, async (url) => {
    checked.push(url);
    return true;
  });

  assert.deepEqual(selected.map((item) => item.id), [1, 2, 3, 4]);
  assert.equal(checked.length, 4);
});

test("hero returns no photo when every eligible image is unavailable", async () => {
  const products = [
    product(1, null),
    product(2, "/uploads/broken.png"),
    { ...product(3, "/uploads/inactive.png"), is_active: false },
    { ...product(4, "/uploads/sold-out.png"), stock: 0 },
  ];
  const selected = await selectHeroProductsWithImages(products, async () => false);
  assert.deepEqual(selected, []);
});

test("image probe accepts portrait and landscape photos and rejects broken images", async () => {
  const originalImage = globalThis.Image;
  class TestImage {
    naturalWidth = 0;
    naturalHeight = 0;
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;

    set src(url: string) {
      queueMicrotask(() => {
        const dimensions = url.includes("portrait")
          ? [400, 800]
          : url.includes("landscape")
            ? [1200, 600]
            : [0, 0];
        [this.naturalWidth, this.naturalHeight] = dimensions;
        if (url.includes("broken")) this.onerror?.();
        else this.onload?.();
      });
    }
  }

  globalThis.Image = TestImage as unknown as typeof Image;
  try {
    assert.equal(await probeProductImage("portrait.png"), true);
    assert.equal(await probeProductImage("landscape.png"), true);
    assert.equal(await probeProductImage("empty.png"), false);
    assert.equal(await probeProductImage("broken.png"), false);
  } finally {
    globalThis.Image = originalImage;
  }
});
