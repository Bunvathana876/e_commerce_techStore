import StoreNavbar from "@/components/store/StoreNavbar";
import MinimalStoreFooter from "@/components/store/MinimalStoreFooter";
import StoreOverlays from "@/components/store/StoreOverlays";
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
      <MinimalStoreFooter />
      <StoreOverlays />
      <ToastViewport />
    </div>
  );
}
