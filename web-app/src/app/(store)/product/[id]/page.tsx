import { SHOWCASE_PRODUCTS } from "@/lib/store-catalog";
import ProductDetailClient from "./ProductDetailClient";

export async function generateStaticParams() {
  return SHOWCASE_PRODUCTS.map((p) => ({
    id: String(p.id),
  }));
}

export const dynamicParams = true;

export default async function ProductDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ProductDetailClient id={id} />;
}
