"use client";

import dynamic from "next/dynamic";
import ToastViewport from "@/components/store/ToastViewport";

const CartDrawer = dynamic(() => import("@/components/store/CartDrawer"), {
  ssr: false,
});
const QuickViewDialog = dynamic(
  () => import("@/components/store/QuickViewDialog"),
  { ssr: false }
);
const SearchCommandDialog = dynamic(
  () => import("@/components/store/SearchCommandDialog"),
  { ssr: false }
);

export default function StoreOverlays() {
  return (
    <>
      <CartDrawer />
      <QuickViewDialog />
      <SearchCommandDialog />
      <ToastViewport />
    </>
  );
}
