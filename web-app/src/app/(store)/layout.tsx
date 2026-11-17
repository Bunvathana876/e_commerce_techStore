import StoreNavbar from "@/components/store/StoreNavbar";
import StoreFooter from "@/components/store/StoreFooter";
import CartDrawer from "@/components/store/CartDrawer";
import QuickViewDialog from "@/components/store/QuickViewDialog";
import SearchCommandDialog from "@/components/store/SearchCommandDialog";
import ToastViewport from "@/components/store/ToastViewport";

export default function StoreLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col text-slate-900">
      <StoreNavbar />
      <main className="flex-1">{children}</main>
      <StoreFooter />
      <CartDrawer />
      <QuickViewDialog />
      <SearchCommandDialog />
      <ToastViewport />
    </div>
  );
}
