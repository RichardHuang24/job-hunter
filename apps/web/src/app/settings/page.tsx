import Link from "next/link";
import AiCard from "@/components/AiCard";
import { ErrorBanner } from "@/components/Feedback";
import TitleCheck from "@/components/TitleCheck";
import { backendGet } from "@/lib/session";
import type { AiStatus, Me, Presets } from "@/lib/types";
import ProfileForm from "./ProfileForm";
import TargetsEditor from "./TargetsEditor";
import YourData from "./YourData";

export default async function SettingsPage() {
  const [me, presets, ai] = await Promise.all([backendGet<Me>("/me"), backendGet<Presets>("/presets"), backendGet<AiStatus>("/me/ai")]);
  if (!me || !presets) return <ErrorBanner message="The API isn't answering. Check that it's running (see the README), then reload." />;
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-2 text-[15px] text-ink-secondary">
          Signed in as {me.email}.{" "}
          {!me.profile?.onboarded_at && (
            <Link href="/onboarding" className="underline underline-offset-2">
              Run the setup
            </Link>
          )}
        </p>
      </div>
      <div className="grid items-start gap-6 lg:grid-cols-[3fr_2fr]">
        <ProfileForm initial={me.profile} presets={presets} />
        <div className="flex flex-col gap-6 lg:sticky lg:top-20">
          <TargetsEditor initial={me.targets} industryKey={me.profile?.industry ?? ""} />
          <TitleCheck />
          {ai && <AiCard ai={ai} />}
          {me.email && <YourData email={me.email} />}
        </div>
      </div>
    </div>
  );
}
