/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_MAP_STYLE_URL?: string;
  readonly VITE_MAP_GLYPHS_URL?: string;
  readonly VITE_MAP_SPRITE_URL?: string;
  readonly VITE_MAP_OFFLINE?: string;
  readonly VITE_E2E?: string;
  readonly VITE_MOTION_DISABLED?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
