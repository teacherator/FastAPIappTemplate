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

type OwnedAppDetails = {
  app: {
    app_name: string;
    created_by: string;
    created_at: string | null;
    collections_count: number;
    members_count: number;
  };
  collections: string[];
  members: Array<{
    email: string;
    type: string;
    primary_app: string;
  }>;
};

type AdminUser = {
  email: string;
  type: string;
  app_name?: string;
  apps?: string[];
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
  const [selectedOwnedApp, setSelectedOwnedApp] = useState<string | null>(null);
  const [ownedAppSubtab, setOwnedAppSubtab] = useState<"overview" | "collections" | "objects" | "members">(
    "overview"
  );
  const [ownedAppDetails, setOwnedAppDetails] = useState<OwnedAppDetails | null>(null);
  const [isLoadingOwnedAppDetails, setIsLoadingOwnedAppDetails] = useState(false);
  const [newCollectionName, setNewCollectionName] = useState("");
  const [objectCollection, setObjectCollection] = useState("");
  const [objectUserId, setObjectUserId] = useState("");
  const [objectJson, setObjectJson] = useState("{}");
  const [deleteObjectCollection, setDeleteObjectCollection] = useState("");
  const [deleteObjectUserId, setDeleteObjectUserId] = useState("");
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
  const [adminUsersFilterApp, setAdminUsersFilterApp] = useState("");
  const [isLoadingAdminUsers, setIsLoadingAdminUsers] = useState(false);
  const [newAdminAppName, setNewAdminAppName] = useState("");
  const [deletingAppNames, setDeletingAppNames] = useState<Record<string, boolean>>({});
  const [activeTab, setActiveTab] = useState<
    "request" | "mine" | "owned" | "open" | "history" | "apps" | "create" | "users"
  >(userType === "admin" ? "open" : "request");
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
      const appsData = data.apps ?? [];
      setOwnedApps(appsData);
      if (!appsData.length) {
        setSelectedOwnedApp(null);
        setOwnedAppDetails(null);
        return;
      }
      const keepSelected = selectedOwnedApp && appsData.some((a) => a.app_name === selectedOwnedApp);
      const nextSelected = keepSelected ? selectedOwnedApp : appsData[0].app_name;
      setSelectedOwnedApp(nextSelected);
      if (nextSelected) {
        loadOwnedAppDetails(nextSelected);
      }
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

  const loadOwnedAppDetails = async (targetAppName: string) => {
    setIsLoadingOwnedAppDetails(true);
    try {
      const response = await fetch(`/my_owned_apps/${encodeURIComponent(targetAppName)}/details`, {
        credentials: "include",
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to load app details");
      }
      const data = (await response.json()) as OwnedAppDetails;
      setOwnedAppDetails(data);
    } catch (error) {
      toast({
        title: "Could not load app details",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
      setOwnedAppDetails(null);
    } finally {
      setIsLoadingOwnedAppDetails(false);
    }
  };

  const loadAdminUsers = async (appFilter?: string) => {
    setIsLoadingAdminUsers(true);
    try {
      const q = appFilter?.trim() ? `?app_name=${encodeURIComponent(appFilter.trim())}` : "";
      const response = await fetch(`/admin/users${q}`, { credentials: "include" });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to load users");
      }
      const data = (await response.json()) as { users: AdminUser[] };
      setAdminUsers(data.users ?? []);
    } catch (error) {
      toast({
        title: "Could not load users",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    } finally {
      setIsLoadingAdminUsers(false);
    }
  };

  const createAdminApp = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    try {
      const formData = new FormData();
      formData.append("app_name", newAdminAppName);
      const response = await fetch("/admin/create_app", {
        method: "POST",
        body: formData,
        credentials: "include",
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to create app");
      }
      setNewAdminAppName("");
      toast({ title: "App created", description: "New app created successfully." });
      loadApps();
    } catch (error) {
      toast({
        title: "Create app failed",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    }
  };

  const adminSetUserRole = async (targetEmail: string, newRole: "user" | "developer" | "admin") => {
    try {
      const formData = new FormData();
      formData.append("target_email", targetEmail);
      formData.append("new_type", newRole);
      if (adminUsersFilterApp.trim()) {
        formData.append("app_name", adminUsersFilterApp.trim());
      }
      const response = await fetch("/admin/users/role", {
        method: "POST",
        body: formData,
        credentials: "include",
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to update user role");
      }
      toast({ title: "Role updated", description: `${targetEmail} is now ${newRole}.` });
      loadAdminUsers(adminUsersFilterApp);
    } catch (error) {
      toast({
        title: "Role update failed",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    }
  };

  const addOwnedCollection = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedOwnedApp) return;
    try {
      const formData = new FormData();
      formData.append("collection_name", newCollectionName);
      const response = await fetch(`/my_owned_apps/${encodeURIComponent(selectedOwnedApp)}/collections`, {
        method: "POST",
        body: formData,
        credentials: "include",
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to add collection");
      }
      setNewCollectionName("");
      toast({ title: "Collection created", description: "Collection added successfully." });
      loadOwnedAppDetails(selectedOwnedApp);
    } catch (error) {
      toast({
        title: "Collection create failed",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    }
  };

  const deleteOwnedCollection = async (collectionName: string) => {
    if (!selectedOwnedApp) return;
    try {
      const response = await fetch(
        `/my_owned_apps/${encodeURIComponent(selectedOwnedApp)}/collections/${encodeURIComponent(collectionName)}`,
        { method: "DELETE", credentials: "include" }
      );
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to delete collection");
      }
      toast({ title: "Collection deleted", description: `${collectionName} removed.` });
      loadOwnedAppDetails(selectedOwnedApp);
    } catch (error) {
      toast({
        title: "Delete collection failed",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    }
  };

  const upsertOwnedObject = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedOwnedApp) return;
    try {
      const formData = new FormData();
      formData.append("collection_name", objectCollection);
      formData.append("userId", objectUserId);
      formData.append("obj", objectJson);
      const response = await fetch(`/my_owned_apps/${encodeURIComponent(selectedOwnedApp)}/objects/upsert`, {
        method: "POST",
        body: formData,
        credentials: "include",
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to upsert object");
      }
      toast({ title: "Object saved", description: "Object upsert completed." });
    } catch (error) {
      toast({
        title: "Object upsert failed",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    }
  };

  const deleteOwnedObject = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedOwnedApp) return;
    try {
      const query = `?collection_name=${encodeURIComponent(deleteObjectCollection)}&user_id=${encodeURIComponent(deleteObjectUserId)}`;
      const response = await fetch(`/my_owned_apps/${encodeURIComponent(selectedOwnedApp)}/objects${query}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to delete object");
      }
      toast({ title: "Object deleted", description: "Object removed." });
    } catch (error) {
      toast({
        title: "Delete object failed",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    }
  };

  const setOwnedUserRole = async (targetEmail: string, newRole: "user" | "developer") => {
    if (!selectedOwnedApp) return;
    try {
      const formData = new FormData();
      formData.append("target_email", targetEmail);
      formData.append("new_type", newRole);
      const response = await fetch(`/my_owned_apps/${encodeURIComponent(selectedOwnedApp)}/users/role`, {
        method: "POST",
        body: formData,
        credentials: "include",
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to update role");
      }
      toast({ title: "Role updated", description: `${targetEmail} is now ${newRole}.` });
      loadOwnedAppDetails(selectedOwnedApp);
    } catch (error) {
      toast({
        title: "Role update failed",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
    }
  };

  const removeOwnedUser = async (targetEmail: string) => {
    if (!selectedOwnedApp) return;
    try {
      const response = await fetch(
        `/my_owned_apps/${encodeURIComponent(selectedOwnedApp)}/users/${encodeURIComponent(targetEmail)}`,
        {
          method: "DELETE",
          credentials: "include",
        }
      );
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to remove user");
      }
      toast({ title: "User removed", description: `${targetEmail} removed from app.` });
      loadOwnedAppDetails(selectedOwnedApp);
    } catch (error) {
      toast({
        title: "Remove user failed",
        description: error instanceof Error ? error.message : "Please try again",
        variant: "destructive",
      });
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
              <Button
                type="button"
                variant={activeTab === "create" ? "default" : "outline"}
                onClick={() => setActiveTab("create")}
              >
                Create App
              </Button>
              <Button
                type="button"
                variant={activeTab === "users" ? "default" : "outline"}
                onClick={() => {
                  setActiveTab("users");
                  loadAdminUsers(adminUsersFilterApp);
                }}
              >
                Users
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
            ) : activeTab === "create" ? (
              <form onSubmit={createAdminApp} className="space-y-3">
                <h3 className="text-lg font-semibold">Create App</h3>
                <Input
                  value={newAdminAppName}
                  onChange={(e) => setNewAdminAppName(e.target.value)}
                  placeholder="App name"
                  required
                />
                <Button type="submit">Create</Button>
              </form>
            ) : activeTab === "users" ? (
              <div className="space-y-3">
                <div className="flex gap-2">
                  <Input
                    value={adminUsersFilterApp}
                    onChange={(e) => setAdminUsersFilterApp(e.target.value)}
                    placeholder="Filter by app name (optional)"
                  />
                  <Button type="button" onClick={() => loadAdminUsers(adminUsersFilterApp)}>
                    Load
                  </Button>
                </div>
                {adminUsers.map((u) => (
                  <div key={`${u.email}-${u.app_name ?? "na"}`} className="border rounded-md p-3 space-y-2">
                    <div className="font-medium">{u.email}</div>
                    <div className="text-sm text-muted-foreground">
                      role: {u.type} | primary: {u.app_name ?? "portal"}
                    </div>
                    <div className="flex gap-2">
                      <Button type="button" variant="outline" onClick={() => adminSetUserRole(u.email, "user")}>
                        Set User
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => adminSetUserRole(u.email, "developer")}
                      >
                        Set Developer
                      </Button>
                      <Button type="button" variant="outline" onClick={() => adminSetUserRole(u.email, "admin")}>
                        Set Admin
                      </Button>
                    </div>
                  </div>
                ))}
                {!isLoadingAdminUsers && adminUsers.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No users to show.</p>
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
              <div className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {ownedApps.map((app) => (
                    <Button
                      key={app.app_name}
                      type="button"
                      variant={selectedOwnedApp === app.app_name ? "default" : "outline"}
                      onClick={() => {
                        setSelectedOwnedApp(app.app_name);
                        setOwnedAppSubtab("overview");
                        loadOwnedAppDetails(app.app_name);
                      }}
                    >
                      {app.app_name}
                    </Button>
                  ))}
                </div>
                {!isLoadingOwnedApps && ownedApps.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No active owned apps.</p>
                ) : null}
                {selectedOwnedApp && ownedAppDetails ? (
                  <div className="border rounded-md p-3 space-y-3">
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        variant={ownedAppSubtab === "overview" ? "default" : "outline"}
                        onClick={() => setOwnedAppSubtab("overview")}
                      >
                        Overview
                      </Button>
                      <Button
                        type="button"
                        variant={ownedAppSubtab === "collections" ? "default" : "outline"}
                        onClick={() => setOwnedAppSubtab("collections")}
                      >
                        Collections
                      </Button>
                      <Button
                        type="button"
                        variant={ownedAppSubtab === "objects" ? "default" : "outline"}
                        onClick={() => setOwnedAppSubtab("objects")}
                      >
                        Objects
                      </Button>
                      <Button
                        type="button"
                        variant={ownedAppSubtab === "members" ? "default" : "outline"}
                        onClick={() => setOwnedAppSubtab("members")}
                      >
                        Members
                      </Button>
                    </div>

                    {ownedAppSubtab === "overview" ? (
                      <div className="space-y-1 text-sm">
                        <div>
                          <span className="font-medium">App:</span> {ownedAppDetails.app.app_name}
                        </div>
                        <div>
                          <span className="font-medium">Created by:</span> {ownedAppDetails.app.created_by}
                        </div>
                        <div>
                          <span className="font-medium">Created at:</span>{" "}
                          {ownedAppDetails.app.created_at ?? "unknown"}
                        </div>
                        <div>
                          <span className="font-medium">Collections:</span>{" "}
                          {ownedAppDetails.app.collections_count}
                        </div>
                        <div>
                          <span className="font-medium">Members:</span> {ownedAppDetails.app.members_count}
                        </div>
                      </div>
                    ) : null}

                    {ownedAppSubtab === "collections" ? (
                      <div className="space-y-2">
                        <form onSubmit={addOwnedCollection} className="flex gap-2">
                          <Input
                            value={newCollectionName}
                            onChange={(e) => setNewCollectionName(e.target.value)}
                            placeholder="New collection name"
                            required
                          />
                          <Button type="submit">Add</Button>
                        </form>
                        {ownedAppDetails.collections.map((col) => (
                          <div key={col} className="text-sm border rounded px-2 py-2 flex justify-between items-center">
                            <span>{col}</span>
                            <Button type="button" variant="destructive" onClick={() => deleteOwnedCollection(col)}>
                              Delete
                            </Button>
                          </div>
                        ))}
                        {ownedAppDetails.collections.length === 0 ? (
                          <p className="text-sm text-muted-foreground">No collections.</p>
                        ) : null}
                      </div>
                    ) : null}

                    {ownedAppSubtab === "objects" ? (
                      <div className="space-y-3">
                        <form onSubmit={upsertOwnedObject} className="space-y-2 border rounded p-3">
                          <div className="font-medium">Upsert Object</div>
                          <Input
                            value={objectCollection}
                            onChange={(e) => setObjectCollection(e.target.value)}
                            placeholder="Collection name"
                            required
                          />
                          <Input
                            value={objectUserId}
                            onChange={(e) => setObjectUserId(e.target.value)}
                            placeholder="userId"
                            required
                          />
                          <textarea
                            value={objectJson}
                            onChange={(e) => setObjectJson(e.target.value)}
                            className="w-full min-h-24 rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm"
                            placeholder='JSON object, e.g. {"plan":"pro"}'
                          />
                          <Button type="submit">Save Object</Button>
                        </form>

                        <form onSubmit={deleteOwnedObject} className="space-y-2 border rounded p-3">
                          <div className="font-medium">Delete Object</div>
                          <Input
                            value={deleteObjectCollection}
                            onChange={(e) => setDeleteObjectCollection(e.target.value)}
                            placeholder="Collection name"
                            required
                          />
                          <Input
                            value={deleteObjectUserId}
                            onChange={(e) => setDeleteObjectUserId(e.target.value)}
                            placeholder="userId"
                            required
                          />
                          <Button type="submit" variant="destructive">
                            Delete Object
                          </Button>
                        </form>
                      </div>
                    ) : null}

                    {ownedAppSubtab === "members" ? (
                      <div className="space-y-2">
                        {ownedAppDetails.members.map((member) => (
                          <div key={member.email} className="text-sm border rounded px-2 py-2 space-y-2">
                            <div>
                              {member.email} | {member.type} | primary: {member.primary_app}
                            </div>
                            <div className="flex gap-2">
                              <Button type="button" variant="outline" onClick={() => setOwnedUserRole(member.email, "user")}>
                                Set User
                              </Button>
                              <Button
                                type="button"
                                variant="outline"
                                onClick={() => setOwnedUserRole(member.email, "developer")}
                              >
                                Set Developer
                              </Button>
                              <Button type="button" variant="destructive" onClick={() => removeOwnedUser(member.email)}>
                                Remove
                              </Button>
                            </div>
                          </div>
                        ))}
                        {ownedAppDetails.members.length === 0 ? (
                          <p className="text-sm text-muted-foreground">No members.</p>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                ) : null}
                {isLoadingOwnedAppDetails ? (
                  <p className="text-sm text-muted-foreground">Loading app details...</p>
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
