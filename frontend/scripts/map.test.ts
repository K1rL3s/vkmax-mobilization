import assert from "node:assert/strict";
import { test } from "node:test";

const tilesUrl = new URL("../src/shared/ui/map/tiles.ts", import.meta.url).href;
const basemapsUrl = new URL("../src/shared/ui/map/basemaps.ts", import.meta.url)
  .href;

const { proxiedUrl, isFatalMapError, hasWebGL } = (await import(tilesUrl)) as {
  proxiedUrl: (url: string, origin: string) => string;
  isFatalMapError: (event: object, styled: boolean) => boolean;
  hasWebGL: () => boolean;
};
const { resolveBasemap, restyleOf, styleOf } = (await import(basemapsUrl)) as {
  resolveBasemap: (
    choice: string,
    scheme: "light" | "dark",
  ) => { id: string; kind: string };
  styleOf: (basemap: unknown) => unknown;
  restyleOf: (basemap: unknown) => (
    previous: undefined,
    next: { layers: { id: string; paint?: object }[] },
  ) => { layers: { id: string; paint?: object }[] };
};

const ORIGIN = "https://vkmax.k1rles.ru";

test("sends every known tile host through our proxy", () => {
  assert.equal(
    proxiedUrl("https://tiles.openfreemap.org/styles/liberty", ORIGIN),
    `${ORIGIN}/tiles/ofm/styles/liberty`,
  );
  assert.equal(
    proxiedUrl("https://tile.openstreetmap.org/12/2476/1284.png", ORIGIN),
    `${ORIGIN}/tiles/osm/12/2476/1284.png`,
  );
});

test("leaves other urls alone", () => {
  assert.equal(
    proxiedUrl("https://st.max.ru/js/max-web-app.js", ORIGIN),
    "https://st.max.ru/js/max-web-app.js",
  );
});

test("auto follows the MAX colour scheme", () => {
  assert.equal(resolveBasemap("auto", "light").id, "light");
  assert.equal(resolveBasemap("auto", "dark").id, "grey");
  assert.equal(resolveBasemap("dark", "dark").id, "dark");
  assert.equal(resolveBasemap("osm", "dark").id, "osm");
});

test("a raster basemap still has glyphs for our labels", () => {
  const style = styleOf(resolveBasemap("osm", "light")) as { glyphs: string };
  assert.match(style.glyphs, /tiles\.openfreemap\.org\/fonts/);
});

test("only a broken style or source hides the map, a broken tile does not", () => {
  const error = new Error("boom");
  assert.equal(isFatalMapError({ error }, false), true);
  assert.equal(
    isFatalMapError({ error, sourceId: "openmaptiles" }, true),
    true,
  );
  assert.equal(
    isFatalMapError({ error, sourceId: "openmaptiles", tile: {} }, true),
    false,
  );
  assert.equal(
    isFatalMapError({ error, sourceId: "base", tile: {} }, false),
    false,
  );
  assert.equal(isFatalMapError({ error }, true), false);
});

test("the WebGL probe gives its context back so it cannot evict the map", () => {
  let released = 0;
  const gl = {
    getExtension: () => ({ loseContext: () => (released += 1) }),
  };
  Object.assign(globalThis, {
    document: { createElement: () => ({ getContext: () => gl }) },
  });

  assert.equal(hasWebGL(), true);
  assert.equal(released, 1);
});

test("the grey basemap repaints the dark style and keeps the rest", () => {
  const next = {
    layers: [
      { id: "background", paint: { "background-color": "rgb(12,12,12)" } },
      { id: "unknown", paint: { "fill-color": "#123456" } },
    ],
  };

  assert.deepEqual(
    restyleOf(resolveBasemap("grey", "dark"))(undefined, next).layers,
    [
      { id: "background", paint: { "background-color": "#2b2b2b" } },
      { id: "unknown", paint: { "fill-color": "#123456" } },
    ],
  );
  assert.equal(
    restyleOf(resolveBasemap("dark", "dark"))(undefined, next),
    next,
  );
});
