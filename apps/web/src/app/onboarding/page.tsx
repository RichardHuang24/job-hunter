import { redirect } from "next/navigation";
import { ErrorBanner } from "@/components/Feedback";
import { backendGet } from "@/lib/session";
import type { Me, Presets } from "@/lib/types";
import OnboardingFlow from "./OnboardingFlow";

export default async function OnboardingPage() {
  const [me, presets] = await Promise.all([backendGet<Me>("/me"), backendGet<Presets>("/presets")]);
  if (!me || !presets) return <ErrorBanner message="The API isn't answering. Check that it's running (see the README), then reload." />;
  if (me.profile?.onboarded_at) redirect("/settings");
  return <OnboardingFlow me={me} presets={presets} />;
}
