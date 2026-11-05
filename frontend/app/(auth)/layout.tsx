export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      <header className="border-b border-zinc-200 bg-white px-6 py-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-zinc-900 dark:text-zinc-50">
            LMS Workspace
          </span>
          <span className="text-xs text-zinc-500">Authenticated Shell</span>
        </div>
      </header>
      <main className="p-6">{children}</main>
    </div>
  );
}

