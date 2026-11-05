import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import Link from "next/link";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6 rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <div className="space-y-1 text-center">
          <h2 className="text-xl font-semibold tracking-tight">Sign In</h2>
          <p className="text-xs text-zinc-500">
            Enter your credentials to access your organization workspace
          </p>
        </div>
        <form className="space-y-4">
          <Input
            label="Email"
            type="email"
            placeholder="you@organization.com"
            autoComplete="email"
            required
          />
          <Input
            label="Password"
            type="password"
            placeholder="••••••••"
            autoComplete="current-password"
            required
          />
          <Button type="button" className="w-full">
            Sign In
          </Button>
        </form>
        <p className="text-center text-xs text-zinc-500">
          Need to onboard a new organization?{" "}
          <Link href="/register" className="text-blue-600 hover:underline">
            Register here
          </Link>
        </p>
      </div>
    </div>
  );
}

