import { EmptyState } from "@/shared/ui/state";
import { pollIcon } from "@/shared/ui/icon";

const MeetingsPage = () => {
  return (
    <EmptyState
      fill
      icon={pollIcon}
      title="Собрания в разработке"
      description="Экран ещё делается. Скоро здесь появятся опросы дома, голосование и результаты."
    />
  );
};

export const Component = MeetingsPage;
