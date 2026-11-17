export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-paper p-4 sm:p-6 lg:p-8">
      <div className="relative z-10 w-full flex justify-center py-6 sm:py-10">
        {children}
      </div>
    </div>
  );
}
