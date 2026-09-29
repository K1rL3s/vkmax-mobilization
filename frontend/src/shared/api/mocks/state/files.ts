export const uploads = new Map<string, string>();

let nextFileId = 1;

export const fileUrl = (name: string): string => uploads.get(name) ?? "";

export const nextFileName = (suffix = "jpg"): string =>
  `upload-${nextFileId++}.${suffix}`;
