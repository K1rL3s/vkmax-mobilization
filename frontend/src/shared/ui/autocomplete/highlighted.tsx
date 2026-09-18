import styles from "./highlighted.module.css";

const escape = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export const Highlighted = ({
  text,
  query,
}: {
  text: string;
  query: string;
}) => {
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);

  if (words.length === 0) {
    return <>{text}</>;
  }

  const parts = text.split(
    new RegExp(`(${words.map(escape).join("|")})`, "gi"),
  );

  return (
    <>
      {parts.map((part, index) =>
        words.includes(part.toLowerCase()) ? (
          <span key={index} className={styles.Match}>
            {part}
          </span>
        ) : (
          part
        ),
      )}
    </>
  );
};
