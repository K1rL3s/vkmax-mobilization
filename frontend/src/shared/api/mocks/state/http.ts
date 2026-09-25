// обработчику приходит express-запрос: кроме разобранных полей у него есть
// непрочитанный поток тела, из которого `multipart.ts` достаёт файл
export type MockHttpRequest = AsyncIterable<Uint8Array> & {
  params: Record<string, string>;
  query: Record<string, string | undefined>;
  body: Record<string, unknown>;
  headers: Record<string, string | undefined>;
};
