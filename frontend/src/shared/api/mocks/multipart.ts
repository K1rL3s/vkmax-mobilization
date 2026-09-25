import type { MockHttpRequest } from "./reply";

export const readUploadedFile = async (
  request: MockHttpRequest,
): Promise<string | null> => {
  const boundary = /boundary=(?:"([^"]+)"|([^\s;]+))/i.exec(
    request.headers["content-type"] ?? "",
  );

  if (!boundary) {
    return null;
  }

  let body = "";

  for await (const chunk of request) {
    for (let at = 0; at < chunk.length; at += 8192) {
      body += String.fromCharCode(...chunk.subarray(at, at + 8192));
    }
  }

  for (const part of body.split(`--${boundary[1] ?? boundary[2]}`)) {
    const split = part.indexOf("\r\n\r\n");

    if (split !== -1 && /filename="/i.test(part.slice(0, split))) {
      const type =
        /content-type:\s*([^\r\n]+)/i.exec(part.slice(0, split))?.[1] ??
        "application/octet-stream";

      return `data:${type};base64,${btoa(part.slice(split + 4, -2))}`;
    }
  }

  return null;
};
