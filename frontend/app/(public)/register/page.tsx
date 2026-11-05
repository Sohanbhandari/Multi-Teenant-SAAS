import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import Link from "next/link";

export default function RegisterPage() {
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6 rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <div className="space-y-1 text-center">
          <h2 className="text-xl font-semibold tracking-tight">Register Organization</h2>
          <p className="text-xs text-zinc-500">
            Create an organization workspace and initial administrator account
          </p>
        </div>
        <form className="space-y-4">
          <Input
            label="Organization Name"
            type="text"
            placeholder="Acme Academy"
            required
          />
          <Input
            label="Organization Slug"
            type="text"
            placeholder="acme-academy"
            hint="Unique tenant identifier"
            required
          />
          <Input
            label="Admin Email"
            type="email"
            placeholder="admin@acme.com"
            autoComplete="email"
            required
          />
          <Input
            label="Admin Password"
            type="password"
            placeholder="••••••••"
            autoComplete="new-password"
            required
          />
          <Button type="button" className="w-full">
            Create Organization
          </Button>
        </form>
        <p className="text-center text-xs text-zinc-500">
          Already registered?{" "}
          <Link href="/login" className="text-blue-600 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

