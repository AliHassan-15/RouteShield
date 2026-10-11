import { useSyncExternalStore } from 'react';

export function useMediaQuery(query: string): boolean {
  const subscribe = (listener: () => void) => {
    const media = typeof matchMedia === 'function' ? matchMedia(query) : null;
    media?.addEventListener('change', listener);
    return () => media?.removeEventListener('change', listener);
  };
  return useSyncExternalStore(subscribe, () => typeof matchMedia === 'function' && matchMedia(query).matches, () => false);
}
export function useReducedMotion() {
  return useMediaQuery('(prefers-reduced-motion: reduce)');
}
export function transitionTheme(update: () => void, reduced: boolean) {
  if (!reduced && document.startViewTransition) {
    const transition = document.startViewTransition(update);
    void transition.finished.catch(() => {});
  } else update();
}
