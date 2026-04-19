import { ReactNode } from "react";

type Props = {
  children: ReactNode;
  className?: string;
};

export default function Card({ children, className = "" }: Props) {
  return (
    <div className={`bg-white rounded-2xl shadow-md border border-gray-100 p-6 ${className}`}>
      {children}
    </div>
  );
}
