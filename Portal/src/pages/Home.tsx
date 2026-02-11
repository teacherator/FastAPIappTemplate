import { Button } from "@/components/ui/button";

type HomeProps = {
  email: string;
  onLogout: () => void;
};

export default function Home({ email, onLogout }: HomeProps) {
  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-xl rounded-xl border bg-card text-card-foreground shadow-sm p-8 space-y-4">
        <h1 className="text-3xl font-bold">Homepage</h1>
        <p className="text-muted-foreground">
          You are logged in as <span className="font-medium text-foreground">{email}</span>.
        </p>
        <Button onClick={onLogout}>Log out</Button>
      </div>
    </div>
  );
}
