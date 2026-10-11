export type SheetSnap = 'peek' | 'half' | 'full';
export const sheetSnaps: readonly SheetSnap[] = ['peek', 'half', 'full'];
export function snapOffset(snap: SheetSnap, height: number) {
  return snap === 'full' ? 0 : snap === 'half' ? height / 2 : Math.max(0, height - 108);
}
export function nearestSnap(offset: number, height: number): SheetSnap {
  return sheetSnaps.reduce((best, snap) => Math.abs(offset - snapOffset(snap, height)) <= Math.abs(offset - snapOffset(best, height)) ? snap : best, 'peek');
}
export function keyboardSnap(snap: SheetSnap, key: string): SheetSnap {
  if (key === 'Escape' || key === 'End') return 'peek';
  if (key === 'Home') return 'full';
  const index = sheetSnaps.indexOf(snap);
  return sheetSnaps[Math.min(2, Math.max(0, index + (key === 'ArrowUp' ? 1 : key === 'ArrowDown' ? -1 : 0)))] ?? snap;
}
