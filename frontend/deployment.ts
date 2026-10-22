/** Build-time policy only. No provider credentials or test hooks enter the client. */
export function productionApiBase(value: string | undefined) {
  const message = 'Production requires VITE_API_BASE_URL=https://<backend-host>/api/v1/ (no localhost, credentials or query).';
  let url: URL;
  try { url = new URL(value ?? ''); } catch { throw Error(message); }
  const host = url.hostname.replace(/\.$/, '');
  if (url.protocol !== 'https:' || /^(localhost|0\.0\.0\.0|127\..*|\[::1\])$|\.localhost$/i.test(host) || url.username || url.password || url.search || url.hash || url.pathname !== '/api/v1/') throw Error(message);
  return url.href;
}
export function securityHeaders(apiBase: string): Record<string, string> {
  const api = new URL(apiBase).origin;
  return {
    'Content-Security-Policy': `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; worker-src 'self' blob:; connect-src 'self' ${api} https://tiles.openfreemap.org; img-src 'self' data: blob: https://tiles.openfreemap.org; font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`,
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
    'X-Frame-Options': 'DENY',
  };
}
export function cloudflareHeaders(apiBase: string) {
  return `/*\n${Object.entries(securityHeaders(apiBase)).map(([k, v]) => `  ${k}: ${v}`).join('\n')}\n/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n/\n  Cache-Control: no-cache\n/index.html\n  Cache-Control: no-cache\n/theme-init.js\n  Cache-Control: no-cache\n`;
}
