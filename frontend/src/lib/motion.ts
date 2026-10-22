import { useSyncExternalStore } from 'react';

export const MOTION = Object.freeze({ fast: 120, normal: 200, long: 240, hero: 300, entrance: 480, camera: 600 });

// One development-only switch for deterministic unit/browser rendering. The
// production build removes this branch, style injection and environment name.
const testOff = import.meta.env.DEV && import.meta.env.VITE_E2E === 'true' && import.meta.env.VITE_MOTION_DISABLED === 'true';
if (testOff && typeof document !== 'undefined') {
  const style = document.createElement('style');
  style.textContent = '/* MOTION_TEST_ONLY */ *,*::before,*::after,::view-transition-old(root),::view-transition-new(root){animation:none!important;transition:none!important;scroll-behavior:auto!important}';
  document.head.append(style);
}
export const motionOff = () => testOff || typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;

export function useMediaQuery(query: string): boolean {
  const subscribe = (listener: () => void) => {
    const media = typeof matchMedia === 'function' ? matchMedia(query) : null;
    media?.addEventListener('change', listener);
    return () => media?.removeEventListener('change', listener);
  };
  return useSyncExternalStore(subscribe, () => typeof matchMedia === 'function' && matchMedia(query).matches, () => false);
}
export function useReducedMotion() {
  const reduced = useMediaQuery('(prefers-reduced-motion: reduce)');
  return testOff || reduced;
}
export function transitionTheme(update: () => void, reduced: boolean) {
  if (!reduced && document.startViewTransition) {
    const transition = document.startViewTransition(update);
    void transition.finished.catch(() => {});
  } else update();
}
