import type { ApiProduct } from "./api";
import { NEUTRAL_PRODUCT_PLACEHOLDER, resolveProductImage } from "./store-catalog";

export type ProductImageProbe = (url: string) => Promise<boolean>;

export function probeProductImage(url: string): Promise<boolean> {
  return new Promise((resolve) => {
    const image = new Image();
    let settled = false;
    const finish = (usable: boolean) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      image.onload = null;
      image.onerror = null;
      resolve(usable);
    };
    const timeout = setTimeout(() => finish(false), 6000);

    image.onload = () => finish(image.naturalWidth > 0 && image.naturalHeight > 0);
    image.onerror = () => finish(false);
    image.src = url;
  });
}

export async function selectHeroProductsWithImages(
  products: ApiProduct[],
  probe: ProductImageProbe = probeProductImage,
  limit = 4
): Promise<ApiProduct[]> {
  const candidates = products.filter(
    (product) =>
      product.is_active !== false &&
      product.stock > 0 &&
      resolveProductImage(product) !== NEUTRAL_PRODUCT_PLACEHOLDER
  );
  const selected: ApiProduct[] = [];

  for (let start = 0; start < candidates.length && selected.length < limit; start += 4) {
    const batch = candidates.slice(start, start + 4);
    const results = await Promise.all(
      batch.map(async (product) => {
        try {
          return await probe(resolveProductImage(product));
        } catch {
          return false;
        }
      })
    );
    batch.forEach((product, index) => {
      if (results[index] && selected.length < limit) selected.push(product);
    });
  }

  return selected;
}
