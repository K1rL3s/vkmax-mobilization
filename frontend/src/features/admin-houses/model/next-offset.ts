type Page = { items: unknown[]; total: number };

// сдвиг следующей страницы для useInfiniteQuery: сколько уже загружено, пока
// загружено меньше, чем всего
export const nextOffset = (last: Page, pages: Page[]) => {
  const loaded = pages.reduce((sum, page) => sum + page.items.length, 0);

  return loaded < last.total ? loaded : undefined;
};
