import { ErrorBanner } from "@/components/Feedback";
import { backendGet } from "@/lib/session";
import type { Me, Presets } from "@/lib/types";
import ProfileForm from "./ProfileForm";

export default async function SettingsPage() {
  const [me, presets] = await Promise.all([backendGet<Me>("/me"), backendGet<Presets>("/presets")]);
  if (!me || !presets) return <ErrorBanner message="The API isn't answering. Check that it's running (see the README), then reload." />;
  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-2 text-[15px] text-ink-secondary">Signed in as {me.email}.</p>
      </div>
      <ProfileForm initial={me.profile} presets={presets} />
    </div>
  );
}
