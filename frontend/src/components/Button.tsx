import { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  children: ReactNode;
};

const variants: Record<Variant, string> = {
  primary:
    "bg-blue-600 hover:bg-blue-700 text-white font-semibold shadow-sm disabled:opacity-50 disabled:cursor-not-allowed",
  secondary:
    "bg-white hover:bg-gray-50 text-gray-700 font-medium border border-gray-300 disabled:opacity-50",
  ghost: "text-gray-500 hover:text-gray-700 hover:bg-gray-100",
};

export default function Button({
  variant = "primary",
  children,
  className = "",
  ...props
}: Props) {
  return (
    <button
      className={`px-5 py-2.5 rounded-xl transition-colors text-sm ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
