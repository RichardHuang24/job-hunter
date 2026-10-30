export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-700 dark:text-red-300">
      {message}
    </div>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-dashed border-edge px-4 py-8 text-center">
      <p className="font-medium">{title}</p>
      <p className="mt-1 text-sm text-ink-secondary">{body}</p>
    </div>
  );
}
