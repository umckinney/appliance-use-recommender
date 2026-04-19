type Props = {
  steps: string[];
  current: number;
};

export default function StepIndicator({ steps, current }: Props) {
  return (
    <ol className="flex items-center w-full mb-8">
      {steps.map((label, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li
            key={label}
            className={`flex items-center ${i < steps.length - 1 ? "flex-1" : ""}`}
          >
            <div className="flex flex-col items-center">
              <span
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold border-2 transition-colors
                  ${done ? "bg-green-500 border-green-500 text-white" : ""}
                  ${active ? "bg-white border-blue-600 text-blue-600" : ""}
                  ${!done && !active ? "bg-white border-gray-300 text-gray-400" : ""}
                `}
              >
                {done ? "✓" : i + 1}
              </span>
              <span
                className={`mt-1 text-xs hidden sm:block ${active ? "text-blue-600 font-medium" : "text-gray-400"}`}
              >
                {label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div
                className={`flex-1 h-0.5 mx-2 transition-colors ${done ? "bg-green-500" : "bg-gray-200"}`}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
