const PROXIED: readonly (readonly [string, string])[] = [
  ["https://tiles.openfreemap.org/", "/tiles/ofm/"],
  ["https://tile.openstreetmap.org/", "/tiles/osm/"],
  ["https://a.tile.opentopomap.org/", "/tiles/topo/"],
];

export const proxiedUrl = (url: string, origin: string): string => {
  const match = PROXIED.find(([upstream]) => url.startsWith(upstream));
  return match ? `${origin}${match[1]}${url.slice(match[0].length)}` : url;
};

export const hasWebGL = (): boolean => {
  if (typeof document === "undefined") return false;
  const canvas = document.createElement("canvas");
  const gl = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
  gl?.getExtension("WEBGL_lose_context")?.loseContext();
  return Boolean(gl);
};

export const isFatalMapError = (event: object, styled: boolean): boolean =>
  !("tile" in event) && (!styled || "sourceId" in event);
