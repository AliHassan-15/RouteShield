import { expect, test } from 'vitest';
import { cloudflareHeaders, productionApiBase, securityHeaders } from '../../deployment';

test.each([undefined, '', 'http://api.example.test/api/v1/', 'https://localhost/api/v1/', 'https://localhost./api/v1/', 'https://127.0.0.1/api/v1/', 'https://api.example.test/api/v1/?key=placeholder', 'https://user:pass@api.example.test/api/v1/'])('rejects unsafe production API configuration: %s', value => {
  expect(() => productionApiBase(value)).toThrow('Production requires VITE_API_BASE_URL');
});
test('production headers scope scripts, workers, external connections and caching', () => {
  const base = productionApiBase('https://api.example.test/api/v1/');
  const headers = securityHeaders(base), policy = headers['Content-Security-Policy']!;
  expect(policy).toContain("script-src 'self';"); expect(policy).not.toContain('unsafe-eval');
  expect(policy).toContain("worker-src 'self' blob:"); expect(policy).toContain('https://api.example.test https://tiles.openfreemap.org');
  expect(policy).toContain("frame-ancestors 'none'"); expect(cloudflareHeaders(base)).toContain('max-age=31536000, immutable');
});
