import type { MockHttpRequest } from "./state";

// mock-config-server ставит парсеры json, urlencoded и text, а multipart
// проходит мимо них: тело запроса в обработчике не разобрано, зато поток ещё
// не прочитан. Читаем его сами - иначе от загруженного фото осталось бы одно
// имя, и на приёмке фото жителя было бы заглушкой
export const readUploadedFile = async (
  request: MockHttpRequest,
): Promise<string | null> => {
  const boundary = /boundary=(?:"([^"]+)"|([^\s;]+))/i.exec(
    request.headers["content-type"] ?? "",
  );

  if (!boundary) {
    return null;
  }

  // байты держим строкой, символ на байт: TextDecoder так не умеет (метка
  // latin1 по стандарту разбирает windows-1252 и ломает старший диапазон), а
  // btoa ждёт как раз такую строку
  let body = "";

  for await (const chunk of request) {
    for (let at = 0; at < chunk.length; at += 8192) {
      body += String.fromCharCode(...chunk.subarray(at, at + 8192));
    }
  }

  for (const part of body.split(`--${boundary[1] ?? boundary[2]}`)) {
    const split = part.indexOf("\r\n\r\n");

    if (split === -1 || !/filename="/i.test(part.slice(0, split))) {
      continue;
    }

    const type =
      /content-type:\s*([^\r\n]+)/i.exec(part.slice(0, split))?.[1] ??
      "application/octet-stream";

    return `data:${type};base64,${btoa(part.slice(split + 4, -2))}`;
  }

  return null;
};
