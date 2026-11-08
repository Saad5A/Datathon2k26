/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend origin (e.g. https://api.example.com), or `demo` for no backend. Required. */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
