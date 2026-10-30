// Server components: the signed-in user's id, and API reads as them.
import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { backendFetch } from "@/lib/backend";

/** proxy.ts already sends signed-out visitors to /signin; this is the backstop. */
export async function userId(): Promise<string> {
  const id = (await auth())?.user?.id;
  if (!id) redirect("/signin");
  return id;
}

/** GET an API path as the signed-in user: the JSON, or null when the API can't answer. */
export async function backendGet<T>(path: string): Promise<T | null> {
  const id = await userId();
  try {
    const response = await backendFetch(id, path);
    if (response.ok) return (await response.json()) as T;
    console.error(`API GET ${path} answered ${response.status}`);
  } catch (error) {
    console.error(`API GET ${path} failed:`, error);
  }
  return null;
}
