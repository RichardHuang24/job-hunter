import type { ReactNode } from "react";

export default function Card({
  title,
  subtitle,
  action,
  className = "",
  children,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={`rounded-xl border border-edge bg-surface p-5 ${className}`}>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="font-medium">{title}</h2>
          {subtitle && <p className="mt-0.5 text-sm text-ink-secondary">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
