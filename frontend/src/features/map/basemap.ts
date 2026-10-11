import type { StyleSpecification } from 'maplibre-gl';
import type { Attribution } from '../../api/types';
import type { Theme } from './contracts';
export const mapConfig = {
  style: import.meta.env.VITE_MAP_STYLE_URL ?? 'https://tiles.openfreemap.org/styles/positron',
  glyphs: import.meta.env.VITE_MAP_GLYPHS_URL ?? 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
  sprite: import.meta.env.VITE_MAP_SPRITE_URL ?? 'https://tiles.openfreemap.org/sprites/ofm_f384/ofm',
  offline: import.meta.env.VITE_MAP_OFFLINE === 'true',
};
export const inkPalette = {
  light: { background: '#f6f3eb', land: '#eeece3', water: '#dedfd7', road: '#bdc4bf', label: '#425660', halo: '#fffdf7' },
  dark: { background: '#101c25', land: '#172730', water: '#22353f', road: '#354d57', label: '#c4cdcb', halo: '#101c25' },
};
export const offlineStyle = (theme: Theme): StyleSpecification => ({ version: 8, sources: {}, layers: [{ id: 'background', type: 'background', paint: { 'background-color': inkPalette[theme].background } }] });
export function transformStyle(style: StyleSpecification, theme: Theme): StyleSpecification {
  const result = structuredClone(style), p = inkPalette[theme];
  result.glyphs = mapConfig.glyphs; result.sprite = mapConfig.sprite;
  result.layers = result.layers.filter(l => l.type !== 'fill-extrusion' && l.type !== 'raster' && !/building|airport|shield|poi|housenumber|highway-name|water.*label|label_other|label_village/.test(l.id)).map(layer => {
    if (layer.type === 'background') layer.paint = { 'background-color': p.background };
    if (layer.type === 'fill') layer.paint = { ...layer.paint, 'fill-color': /water/.test(layer.id) ? p.water : p.land, 'fill-opacity': .65 };
    if (layer.type === 'line') layer.paint = { ...layer.paint, 'line-color': /water/.test(layer.id) ? p.water : p.road, 'line-opacity': .65 };
    if (layer.type === 'symbol') { layer.layout = { ...layer.layout }; delete layer.layout['icon-image']; layer.paint = { ...layer.paint, 'text-color': p.label, 'text-halo-color': p.halo, 'text-halo-width': 1.5 }; }
    return layer;
  });
  return result;
}
export function attributionEntries(styleHtml: string[], api: Attribution[]) {
  return { html: [...new Set(styleHtml)], providers: api.filter((a, i) => api.findIndex(b => b.provider === a.provider && b.text === a.text) === i) };
}
// Preserve official strings as text/links, never inject remote HTML.
export function creditParts(html: string) {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  return [...doc.body.childNodes].map(node => {
    const link = node instanceof HTMLAnchorElement ? node : null;
    let href: string | undefined;
    try { const u = new URL(link?.href ?? ''); if (u.protocol === 'https:' && /(^|\.)(openfreemap.org|openmaptiles.org|openstreetmap.org)$/.test(u.hostname)) href = u.href; } catch { /* Credit text stays visible. */ }
    return { text: node.textContent ?? '', href };
  });
}
