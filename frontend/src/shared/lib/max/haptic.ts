type Feedback = NonNullable<NonNullable<Window["WebApp"]>["HapticFeedback"]>;

const vibrate = (play: (feedback: Feedback) => Promise<unknown>) => {
  const feedback = window.WebApp?.HapticFeedback;

  if (feedback) {
    void Promise.resolve(feedback)
      .then(play)
      .catch(() => undefined);
  }
};

export const haptic = {
  success: () =>
    vibrate((feedback) => feedback.notificationOccurred("success")),
  error: () => vibrate((feedback) => feedback.notificationOccurred("error")),
  select: () => vibrate((feedback) => feedback.selectionChanged()),
};
