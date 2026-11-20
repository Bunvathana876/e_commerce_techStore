import StoreNavbar from "@/components/store/StoreNavbar";
import StoreFooter from "@/components/store/StoreFooter";
import StoreOverlays from "@/components/store/StoreOverlays";

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
      <StoreOverlays />
    </div>
  );
}
