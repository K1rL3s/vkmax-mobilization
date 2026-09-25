export const uploads = new Map<string, string>();

let nextFileId = 1;

export const fileUrl = (name: string): string => uploads.get(name) ?? "";

export const nextFileName = (): string => `upload-${nextFileId++}.jpg`;
