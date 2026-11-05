import Link from "next/link";
import { Button } from "@/components/ui/Button";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8 text-center">
      <div className="max-w-md space-y-4">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
          Learning & Coaching SaaS
        </h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          A multi-tenant learning and coaching management platform.
        </p>
        <div className="flex justify-center gap-4 pt-4">
          <Link href="/login">
            <Button variant="primary">Log In</Button>
          </Link>
          <Link href="/register">
            <Button variant="outline">Register Org</Button>
          </Link>
        </div>
      </div>
    </main>
  );
}

