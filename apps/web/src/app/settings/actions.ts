"use server";

import { auth, signOut } from "@/auth";
import { backendFetch } from "@/lib/backend";

export type DeleteState = { error: string | null };

/** Deletes the signed-in account (DELETE /me), then signs out. */
export async function deleteAccount(_previous: DeleteState, form: FormData): Promise<DeleteState> {
  const userId = (await auth())?.user?.id;
  if (!userId) return { error: "You've been signed out. Sign in again." };
  let response: Response;
  try {
    response = await backendFetch(userId, "/me", {
      method: "DELETE",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ confirm: String(form.get("confirm") ?? "") }),
    });
  } catch {
    return { error: "The API isn't reachable right now. Nothing was deleted." };
  }
  if (response.status !== 204) {
    const detail = ((await response.json().catch(() => ({}))) as { detail?: unknown }).detail;
    return { error: typeof detail === "string" ? detail : "Couldn't delete the account. Nothing was deleted." };
  }
  await signOut({ redirectTo: "/signin?deleted=1" });
  return { error: null };
}
