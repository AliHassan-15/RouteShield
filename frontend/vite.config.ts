import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';
import { cloudflareHeaders, productionApiBase, securityHeaders } from './deployment.ts';

export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, fileURLToPath(new URL('.', import.meta.url)), 'VITE_');
  const api = command === 'build' && mode === 'production' ? productionApiBase(env.VITE_API_BASE_URL) : env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1/';
  if (command === 'build' && mode === 'production') for (const key of ['VITE_MAP_STYLE_URL', 'VITE_MAP_GLYPHS_URL', 'VITE_MAP_SPRITE_URL']) {
    if (env[key] && new URL(env[key]).origin !== 'https://tiles.openfreemap.org') throw Error(`${key} must use https://tiles.openfreemap.org to match the deployment CSP.`);
  }
  return {
    plugins: [react(), {
      name: 'deployment-headers',
      generateBundle() { this.emitFile({ type: 'asset', fileName: '_headers', source: cloudflareHeaders(api) }); },
      // Preview does not interpret Cloudflare _headers; apply the SAME policy locally.
      configurePreviewServer(server) { server.middlewares.use((req, res, next) => {
        for (const [key, value] of Object.entries(securityHeaders(api))) res.setHeader(key, value);
        res.setHeader('Cache-Control', req.url?.startsWith('/assets/') ? 'public, max-age=31536000, immutable' : 'no-cache'); next();
      }); },
    }],
    // Only the public backend base is embedded; unrelated VITE_* secrets are excluded.
    envPrefix: 'ROUTESHIELD_PUBLIC_UNUSED_',
    define: Object.fromEntries(['VITE_API_BASE_URL', 'VITE_MAP_STYLE_URL', 'VITE_MAP_GLYPHS_URL', 'VITE_MAP_SPRITE_URL', 'VITE_MAP_OFFLINE', 'VITE_E2E', 'VITE_MOTION_DISABLED'].filter(key => mode !== 'test' || !['VITE_E2E', 'VITE_MOTION_DISABLED'].includes(key)).map(key => [`import.meta.env.${key}`, JSON.stringify(key === 'VITE_API_BASE_URL' ? api : env[key])])),
    server: { host: '127.0.0.1', port: 5173, strictPort: true },
    preview: { host: '127.0.0.1', port: 4173, strictPort: true },
    test: { environment: 'jsdom', include: ['src/**/*.test.tsx', 'src/**/*.test.ts'] },
  };
});
