import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";

type AppRequest = {
  id: string;
  requested_app_name: string;
  requested_by: string;
  requested_from_app: string;
  reason: string;
  status: "pending" | "approved" | "denied";
  created_at: string | null;
  reviewed_at: string | null;
  reviewed_by: string | null;
};

type AdminApp = {
  app_name: string;
  created_by: string;
  created_at: string | null;
  users_count: number;
};

type OwnedApp = {
  app_name: string;
  created_at: string | null;
};

type HomeProps = {
  email: string;
  userType: string;
  onLogout: () => void;
};

export default function Home({ email, userType, onLogout }: HomeProps) {
  const [appName, setAppName] = useState("");
  const [reason, setReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [requests, setRequests] = useState<AppRequest[]>([]);
  const [isLoadingRequests, setIsLoadingRequests] = useState(false);
  const [apps, setApps] = useState<AdminApp[]>([]);
  const [isLoadingApps, setIsLoadingApps] = useState(false);
  const [ownedApps, setOwnedApps] = useState<OwnedApp[]>([]);
  const [isLoadingOwnedApps, setIsLoadingOwnedApps] = useState(false);
  const [deletingAppNames, setDeletingAppNames] = useState<Record<string, boolean>>({});
  const [activeTab, setActiveTab] = useState<"request" | "mine" | "owned" | "open" | "history" | "apps">(
    userType === "admin" ? "open" : "request"
  );
  const [reviewingIds, setReviewingIds] = useState<Record<string, boolean>>({});
  const { toast } = useToast();

  const loadRequests = async (statusFilter?: "pending" | "approved" | "denied") => {
    setIsLoadingRequests(true);
    try {
      const query = statusFilter ? `?status_filter=${statusFilter}` : "";
      const response = await fetch(`/app_creation_requests${query}`, {
        credentials: "include",
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to load requests");
      }
      const data = (await response.json()) as { requests: AppRequest[] };
      setRequests(data.requests ?? []);
    } catch (error) {
      toast({
        title: "Could not load requests",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    } finally {
      setIsLoadingRequests(false);
    }
  };

  const loadApps = async () => {
    setIsLoadingApps(true);
    try {
      const response = await fetch("/admin/apps", { credentials: "include" });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to load apps");
      }
      const data = (await response.json()) as { apps: AdminApp[] };
      setApps(data.apps ?? []);
    } catch (error) {
      toast({
        title: "Could not load apps",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    } finally {
      setIsLoadingApps(false);
    }
  };

  const loadOwnedApps = async () => {
    setIsLoadingOwnedApps(true);
    try {
      const response = await fetch("/my_owned_apps", { credentials: "include" });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to load owned apps");
      }
      const data = (await response.json()) as { apps: OwnedApp[] };
      setOwnedApps(data.apps ?? []);
    } catch (error) {
      toast({
        title: "Could not load owned apps",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    } finally {
      setIsLoadingOwnedApps(false);
    }
  };

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
      loadRequests();
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

  const reviewRequest = async (requestId: string, status: "approved" | "denied") => {
    setReviewingIds((prev) => ({ ...prev, [requestId]: true }));
    try {
      const formData = new FormData();
      formData.append("status", status);
      const response = await fetch(`/app_creation_requests/${requestId}/status`, {
        method: "POST",
        body: formData,
        credentials: "include",
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to mark request as ${status}`);
      }
      toast({
        title: `Request ${status}`,
        description: "The request status was updated.",
      });
      loadRequests(activeTab === "open" ? "pending" : undefined);
    } catch (error) {
      toast({
        title: "Review failed",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    } finally {
      setReviewingIds((prev) => ({ ...prev, [requestId]: false }));
    }
  };

  const deleteApp = async (appNameToDelete: string) => {
    setDeletingAppNames((prev) => ({ ...prev, [appNameToDelete]: true }));
    try {
      const response = await fetch(`/admin/apps/${encodeURIComponent(appNameToDelete)}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to delete app");
      }
      toast({
        title: "App deleted",
        description: `${appNameToDelete} was deleted successfully.`,
      });
      loadApps();
    } catch (error) {
      toast({
        title: "Delete failed",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    } finally {
      setDeletingAppNames((prev) => ({ ...prev, [appNameToDelete]: false }));
    }
  };

  const pendingRequests = requests.filter((request) => request.status === "pending");
  const reviewedRequests = requests.filter((request) => request.status !== "pending");

  useEffect(() => {
    if (userType === "admin") {
      loadRequests("pending");
    }
  }, [userType]);

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-3xl rounded-xl border bg-card text-card-foreground shadow-sm p-8 space-y-6">
        <h1 className="text-3xl font-bold">Homepage</h1>
        <p className="text-muted-foreground">
          You are logged in as <span className="font-medium text-foreground">{email}</span>.
        </p>

        {userType === "admin" ? (
          <div className="space-y-4 border rounded-lg p-4">
            <div className="flex gap-2">
              <Button
                type="button"
                variant={activeTab === "open" ? "default" : "outline"}
                onClick={() => {
                  setActiveTab("open");
                  loadRequests("pending");
                }}
              >
                Open Requests
              </Button>
              <Button
                type="button"
                variant={activeTab === "history" ? "default" : "outline"}
                onClick={() => {
                  setActiveTab("history");
                  loadRequests();
                }}
              >
                History
              </Button>
              <Button
                type="button"
                variant={activeTab === "apps" ? "default" : "outline"}
                onClick={() => {
                  setActiveTab("apps");
                  loadApps();
                }}
              >
                Apps
              </Button>
            </div>

            {activeTab === "apps" ? (
              <div className="space-y-3">
                {apps.map((app) => (
                  <div key={app.app_name} className="border rounded-md p-3 space-y-2">
                    <div className="font-semibold">{app.app_name}</div>
                    <div className="text-sm text-muted-foreground">
                      Created by {app.created_by} | Users: {app.users_count}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Created at: {app.created_at ?? "unknown"}
                    </div>
                    <Button
                      type="button"
                      variant="destructive"
                      onClick={() => deleteApp(app.app_name)}
                      disabled={!!deletingAppNames[app.app_name]}
                    >
                      Delete App
                    </Button>
                  </div>
                ))}
                {!isLoadingApps && apps.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No apps to show.</p>
                ) : null}
              </div>
            ) : (
              <div className="space-y-3">
                {(activeTab === "open" ? pendingRequests : reviewedRequests).map((request) => (
                  <div key={request.id} className="border rounded-md p-3 space-y-2">
                    <div className="font-semibold">{request.requested_app_name}</div>
                    <div className="text-sm text-muted-foreground">
                      Requested by {request.requested_by} from {request.requested_from_app}
                    </div>
                    {request.reason ? <div className="text-sm">{request.reason}</div> : null}
                    <div className="text-xs text-muted-foreground">Status: {request.status}</div>
                    {activeTab === "open" ? (
                      <div className="flex gap-2">
                        <Button
                          type="button"
                          onClick={() => reviewRequest(request.id, "approved")}
                          disabled={!!reviewingIds[request.id]}
                        >
                          Approve
                        </Button>
                        <Button
                          type="button"
                          variant="destructive"
                          onClick={() => reviewRequest(request.id, "denied")}
                          disabled={!!reviewingIds[request.id]}
                        >
                          Deny
                        </Button>
                      </div>
                    ) : null}
                  </div>
                ))}
                {!isLoadingRequests &&
                (activeTab === "open" ? pendingRequests.length === 0 : reviewedRequests.length === 0) ? (
                  <p className="text-sm text-muted-foreground">No requests to show.</p>
                ) : null}
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4 border rounded-lg p-4">
            <div className="flex gap-2">
              <Button
                type="button"
                variant={activeTab === "request" ? "default" : "outline"}
                onClick={() => setActiveTab("request")}
              >
                Request App
              </Button>
              <Button
                type="button"
                variant={activeTab === "mine" ? "default" : "outline"}
                onClick={() => {
                  setActiveTab("mine");
                  loadRequests();
                }}
              >
                My Requests
              </Button>
              {userType === "developer" ? (
                <Button
                  type="button"
                  variant={activeTab === "owned" ? "default" : "outline"}
                  onClick={() => {
                    setActiveTab("owned");
                    loadOwnedApps();
                  }}
                >
                  Owned Apps
                </Button>
              ) : null}
            </div>

            {activeTab === "request" ? (
              <form onSubmit={submitRequest} className="space-y-3">
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
            ) : activeTab === "owned" ? (
              <div className="space-y-3">
                {ownedApps.map((app) => (
                  <div key={app.app_name} className="border rounded-md p-3 space-y-1">
                    <div className="font-semibold">{app.app_name}</div>
                    <div className="text-xs text-muted-foreground">
                      Created at: {app.created_at ?? "unknown"}
                    </div>
                  </div>
                ))}
                {!isLoadingOwnedApps && ownedApps.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No active owned apps.</p>
                ) : null}
              </div>
            ) : (
              <div className="space-y-3">
                {requests.map((request) => (
                  <div key={request.id} className="border rounded-md p-3 space-y-1">
                    <div className="font-semibold">{request.requested_app_name}</div>
                    <div className="text-sm text-muted-foreground">Status: {request.status}</div>
                    {request.reason ? <div className="text-sm">{request.reason}</div> : null}
                  </div>
                ))}
                {!isLoadingRequests && requests.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No requests yet.</p>
                ) : null}
              </div>
            )}
          </div>
        )}

        <Button onClick={onLogout}>Log out</Button>
      </div>
    </div>
  );
}
