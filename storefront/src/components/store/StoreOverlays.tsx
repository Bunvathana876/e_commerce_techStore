"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useShopStore } from "@/lib/store";

const CartDrawer = dynamic(() => import("./CartDrawer"), { ssr: false });
const QuickViewDialog = dynamic(() => import("./QuickViewDialog"), { ssr: false });
const SearchCommandDialog = dynamic(() => import("./SearchCommandDialog"), { ssr: false });

export default function StoreOverlays() {
  const cartOpen = useShopStore((state) => state.isCartOpen);
  const searchOpen = useShopStore((state) => state.isSearchOpen);
  const quickViewOpen = useShopStore((state) => state.quickViewProduct !== null);
  const [loaded, setLoaded] = useState({ cart: false, search: false, quickView: false });

  // Keep opened dialogs mounted so input state and native focus restoration survive closing.
  useEffect(() => {
    setLoaded((previous) => {
      if ((!cartOpen || previous.cart) && (!searchOpen || previous.search) &&
          (!quickViewOpen || previous.quickView)) return previous;
      return {
        cart: previous.cart || cartOpen,
        search: previous.search || searchOpen,
        quickView: previous.quickView || quickViewOpen,
      };
    });
  }, [cartOpen, searchOpen, quickViewOpen]);

  // This shortcut must be available before the search dialog bundle has loaded.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        const state = useShopStore.getState();
        if (state.isSearchOpen) state.closeSearch();
        else state.openSearch();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <>
      {(cartOpen || loaded.cart) && <CartDrawer />}
      {(quickViewOpen || loaded.quickView) && <QuickViewDialog />}
      {(searchOpen || loaded.search) && <SearchCommandDialog />}
    </>
  );
}
