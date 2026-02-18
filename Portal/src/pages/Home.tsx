import { useState } from "react";
import type { FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";

type HomeProps = {
  email: string;
  onLogout: () => void;
};

export default function Home({ email, onLogout }: HomeProps) {
  const [appName, setAppName] = useState("");
  const [reason, setReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { toast } = useToast();

  const submitRequest = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      const formData = new FormData();
      formData.append("app_name", appName);
      if (reason.trim()) {
        formData.append("reason", reason.trim());
      }

      const response = await fetch("/request_app_creation", {
        method: "POST",
        body: formData,
        credentials: "include",
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to submit request");
      }

      setAppName("");
      setReason("");
      toast({
        title: "Request submitted",
        description: "Your app request has been saved for review.",
      });
    } catch (error) {
      toast({
        title: "Request failed",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-xl rounded-xl border bg-card text-card-foreground shadow-sm p-8 space-y-6">
        <h1 className="text-3xl font-bold">Homepage</h1>
        <p className="text-muted-foreground">
          You are logged in as <span className="font-medium text-foreground">{email}</span>.
        </p>
        <form onSubmit={submitRequest} className="space-y-3 border rounded-lg p-4">
          <h2 className="text-xl font-semibold">Request New App</h2>
          <Input
            value={appName}
            onChange={(e) => setAppName(e.target.value)}
            placeholder="App name (e.g. my_new_app)"
            required
          />
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Reason (optional)"
            className="w-full min-h-24 rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm"
          />
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Submitting..." : "Submit Request"}
          </Button>
        </form>
        <Button onClick={onLogout}>Log out</Button>
      </div>
    </div>
  );
}
