export default function Spinner({ size = "sm" }: { size?: "sm" | "md" }) {
  const dim = size === "sm" ? "w-4 h-4 border-2" : "w-6 h-6 border-2";
  return (
    <div
      className={`${dim} border-blue-500 border-t-transparent rounded-full animate-spin`}
      role="status"
      aria-label="Loading"
    />
  );
}
