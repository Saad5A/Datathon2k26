import { Settings2 } from 'lucide-react'

/** Full-screen failure shown instead of a blank page when required config is missing. */
export function ConfigError({ message }: { message: string }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-6 px-4 py-12 sm:px-6">
      <span className="flex size-10 items-center justify-center rounded-md bg-sev-p0 text-white">
        <Settings2 className="size-5" aria-hidden />
      </span>
      <div>
        <h1 className="text-xl font-semibold tracking-tight">This deployment is not configured</h1>
        <p role="alert" className="mt-2 text-fg-muted">
          {message}
        </p>
      </div>
      <ol className="list-decimal space-y-2 pl-5 text-fg-muted">
        <li>
          Set <code className="font-mono text-fg">VITE_API_URL</code> in your host&rsquo;s environment variables (Vercel: Project
          Settings → Environment Variables; Netlify: Site configuration → Environment variables). Use the backend origin, for
          example <code className="font-mono text-fg">https://api.example.com</code>, or <code className="font-mono text-fg">demo</code> to
          run with sample data and no backend.
        </li>
        <li>
          <strong className="font-medium text-fg">Redeploy.</strong> Vite bakes the value in at build time, so changing it
          without rebuilding has no effect.
        </li>
        <li>
          Running locally? Copy <code className="font-mono text-fg">.env.example</code> to{' '}
          <code className="font-mono text-fg">.env.local</code> and restart the dev server.
        </li>
      </ol>
    </main>
  )
}
