// файлы, загруженные мультипартом: их адреса спрашивают и заявки, и
// показания счётчиков, поэтому предмет отдельный
const state = {
  files: new Map<string, string>(),
  nextFileId: 1,
};

export const resetFiles = (): void => {
  state.files = new Map();
  state.nextFileId = 1;
};

export const saveFile = (name: string, url: string): void => {
  state.files.set(name, url);
};

export const fileUrl = (name: string): string => state.files.get(name) ?? "";

export const nextFileName = (): string => {
  const name = `upload-${state.nextFileId}.jpg`;
  state.nextFileId += 1;

  return name;
};
