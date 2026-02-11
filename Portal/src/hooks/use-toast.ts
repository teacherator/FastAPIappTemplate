// Portal/src/hooks/use-toast.ts
type ToastArgs = {
  title?: string;
  description?: string;
  variant?: "default" | "destructive";
};

export function useToast() {
  return {
    toast: ({ title, description }: ToastArgs) => {
      const msg = [title, description].filter(Boolean).join("\n");
      alert(msg || "Toast");
    },
  };
}
