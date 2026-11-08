import { Compass } from 'lucide-react'

export function NotFound({ path }: { path: string }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-6 px-4 py-12 sm:px-6">
      <span className="flex size-10 items-center justify-center rounded-md bg-raised text-fg-muted">
        <Compass className="size-5" aria-hidden />
      </span>
      <div>
        <p className="font-mono text-sm text-fg-subtle">404</p>
        <h1 className="mt-1 text-xl font-semibold tracking-tight">Page not found</h1>
        <p className="mt-2 text-fg-muted">
          There is nothing at <code className="break-all font-mono text-fg">{path}</code>. The triage dashboard lives at the
          root.
        </p>
      </div>
      <a
        href="/"
        className="inline-flex h-9 w-fit items-center rounded-md bg-fg px-4 text-sm font-medium text-bg hover:bg-fg/90"
      >
        Back to the dashboard
      </a>
    </main>
  )
}
