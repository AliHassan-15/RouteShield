import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  // Only the public backend base is embedded; unrelated VITE_* secrets are excluded.
  envPrefix: 'ROUTESHIELD_PUBLIC_UNUSED_',
  define: Object.fromEntries(['VITE_API_BASE_URL', 'VITE_MAP_STYLE_URL', 'VITE_MAP_GLYPHS_URL', 'VITE_MAP_SPRITE_URL', 'VITE_MAP_OFFLINE', 'VITE_E2E', 'VITE_MOTION_DISABLED'].filter(key => mode !== 'test' || !['VITE_E2E', 'VITE_MOTION_DISABLED'].includes(key)).map(key => [`import.meta.env.${key}`, JSON.stringify(loadEnv(mode, fileURLToPath(new URL('.', import.meta.url)), key)[key] ?? (key === 'VITE_API_BASE_URL' ? 'http://localhost:8000/api/v1/' : undefined))])),
  server: { host: '127.0.0.1', port: 5173, strictPort: true },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true },
  test: { environment: 'jsdom', include: ['src/**/*.test.tsx', 'src/**/*.test.ts'] },
}));
