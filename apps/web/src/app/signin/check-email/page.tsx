import Link from "next/link";

export default function CheckEmailPage() {
  return (
    <div className="mx-auto flex max-w-sm flex-col gap-3 pt-10">
      <h1 className="text-3xl font-semibold tracking-tight">Check your email</h1>
      <p className="text-[15px] text-ink-secondary">
        A sign-in link is on its way. It works once and expires in 24 hours. Running locally? Open Mailpit at{" "}
        <a href="http://localhost:8025" className="underline underline-offset-2">
          localhost:8025
        </a>
        .
      </p>
      <Link href="/signin" className="text-sm text-ink-secondary underline underline-offset-2">
        Use a different email
      </Link>
    </div>
  );
}
