import Link from "next/link";
import { auth, signOut } from "@/auth";
import NavLinks from "./NavLinks";

/** Whether to show the Admin link. The API decides who's an admin (ADMIN_EMAILS); this only hides a link. */
function isAdmin(email: string | null | undefined): boolean {
  const admins = (process.env.ADMIN_EMAILS ?? "").split(",").map((e) => e.trim().toLowerCase()).filter(Boolean);
  return Boolean(email) && admins.includes(email!.toLowerCase());
}

/** The top bar: stays at the top while the page scrolls. Links only once signed in. */
export default async function Nav() {
  const session = await auth();
  return (
    <header className="sticky top-0 z-30 border-b border-edge bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-2 px-4 sm:gap-8 sm:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2.5" aria-label="Job Hunter - home">
          <span
            aria-hidden
            className="grid size-7 place-items-center rounded-lg bg-foreground text-[11px] font-bold tracking-tight text-background"
          >
            JH
          </span>
          <span className="hidden text-[15px] font-semibold tracking-tight sm:inline">Job Hunter</span>
        </Link>
        {session?.user && (
          <>
            <NavLinks admin={isAdmin(session.user.email)} />
            <form
              className="ml-auto flex items-center gap-3 text-sm"
              action={async () => {
                "use server";
                await signOut({ redirectTo: "/signin" });
              }}
            >
              <span className="hidden max-w-48 truncate text-ink-secondary md:inline">{session.user.email}</span>
              <button type="submit" className="rounded-lg px-2 py-1.5 whitespace-nowrap text-ink-secondary hover:bg-ink/[0.04] hover:text-ink sm:px-2.5">
                Sign out
              </button>
            </form>
          </>
        )}
      </div>
    </header>
  );
}
