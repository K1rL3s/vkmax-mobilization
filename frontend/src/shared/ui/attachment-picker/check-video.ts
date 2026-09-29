export const checkVideo = async (
  file: File,
  videoCount: number,
): Promise<void> => {
  if (!file.type.startsWith("video/")) return;
  if (!["video/mp4", "video/quicktime"].includes(file.type)) {
    throw new Error("Поддерживаются только видео MP4 или MOV");
  }
  if (videoCount >= 2) throw new Error("Можно приложить не больше 2 видео");
  if (file.size > 50 * 1024 * 1024) throw new Error("Видео больше 50 МБ");

  await new Promise<void>((resolve, reject) => {
    const video = document.createElement("video");
    const url = URL.createObjectURL(file);
    const finish = (error?: string) => {
      clearTimeout(timeout);
      video.onloadedmetadata = null;
      video.onerror = null;
      video.removeAttribute("src");
      video.load();
      URL.revokeObjectURL(url);
      if (error) reject(new Error(error));
      else resolve();
    };
    const timeout = setTimeout(
      () => finish("Не удалось прочитать видео. Попробуйте MP4"),
      10000,
    );
    video.preload = "metadata";
    video.onloadedmetadata = () => {
      if (!Number.isFinite(video.duration) || video.duration <= 0) {
        finish("Не удалось определить длительность видео");
      } else {
        finish(video.duration > 60 ? "Видео длиннее 60 секунд" : undefined);
      }
    };
    video.onerror = () => finish("Не удалось прочитать видео. Попробуйте MP4");
    video.src = url;
  });
};
