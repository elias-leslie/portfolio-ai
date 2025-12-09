"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function WorkflowsRedirect() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to capabilities page with workflows tab
    router.replace("/capabilities?tab=workflows");
  }, [router]);

  return null;
}
