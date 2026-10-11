import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  // Only the public backend base is embedded; unrelated VITE_* secrets are excluded.
  envPrefix: 'ROUTESHIELD_PUBLIC_UNUSED_',
  define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify(loadEnv(mode, fileURLToPath(new URL('.', import.meta.url)), 'VITE_API_BASE_URL').VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1/') },
  server: { host: '127.0.0.1', port: 5173, strictPort: true },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true },
  test: { environment: 'jsdom', include: ['src/**/*.test.tsx', 'src/**/*.test.ts'] },
}));
