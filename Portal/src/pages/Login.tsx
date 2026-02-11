import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} 
from "@/components/ui/form";
import { useToast } from "@/hooks/use-toast";
import { Loader2, LogIn, CheckCircle2} from "lucide-react";
import { Link, useLocation } from "wouter";

const loginSchema = z.object({
  email: z.string().email("Please enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormData = z.infer<typeof loginSchema>;

export default function Login() {
  const [, navigate] = useLocation();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const { toast } = useToast();

  const form = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const onSubmit = async (data: LoginFormData) => {
    setIsSubmitting(true);
    setIsSuccess(false);

    try {
      const formData = new FormData();
      formData.append("email", data.email);
      formData.append("password", data.password);

      const response = await fetch("https://api.sizebud.com/login", {
        method: "POST",
        body: formData,
        credentials: "include",
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Login failed");
      }

      await response.json();
      localStorage.setItem("email", data.email);
      setIsSuccess(true);

      toast({
        title: "Login successful!",
        description: `Welcome back!`,
      });

      setTimeout(() => {
        window.location.href = "/portal/";
      }, 1500);
    } catch (error) {
      toast({
        title: "Login failed",
        description:
          error instanceof Error
            ? error.message
            : "Please check your credentials",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* Background Gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-background to-accent/5"></div>

      {/* Grid Pattern */}
      <div
        className="absolute inset-0 opacity-[0.02]"
        style={{
          backgroundImage: `
          linear-gradient(to right, hsl(var(--primary)) 1px, transparent 1px),
          linear-gradient(to bottom, hsl(var(--primary)) 1px, transparent 1px)
        `,
          backgroundSize: "4rem 4rem",
        }}
      ></div>

      <div className="relative z-10 min-h-screen flex flex-col items-center justify-center p-4">

        <Card className="w-full max-w-lg border-2 shadow-lg">
          <CardContent className="p-12">
            {isSuccess ? (
              <div className="text-center space-y-8">
                <div className="mx-auto w-20 h-20 rounded-full bg-green-500/10 flex items-center justify-center">
                  <CheckCircle2 className="h-10 w-10 text-green-600" />
                </div>
                <div className="space-y-3">
                  <h3 className="text-3xl font-display font-bold">
                    Welcome Back!
                  </h3>
                  <p className="text-muted-foreground text-lg">
                    Redirecting you to your dashboard...
                  </p>
                </div>
              </div>
            ) : (
              <>
                {/* Header */}
                <div className="text-center space-y-4 mb-10">
                  <div className="mx-auto w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center">
                    <LogIn className="h-8 w-8 text-primary" />
                  </div>
                  <div>
                    <h1 className="text-4xl font-display font-bold mb-2">
                      Welcome Back
                    </h1>
                    <p className="text-muted-foreground text-lg">
                      Sign in to your SizeBud account
                    </p>
                  </div>
                </div>

                {/* Form */}
                <Form {...form}>
                  <form
                    onSubmit={form.handleSubmit(onSubmit)}
                    className="space-y-6"
                  >
                    <FormField
                      control={form.control}
                      name="email"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-base">
                            Email Address
                          </FormLabel>
                          <FormControl>
                            <Input
                              type="email"
                              placeholder="you@example.com"
                              {...field}
                              data-testid="input-email"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="password"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel className="text-base">Password</FormLabel>
                          <FormControl>
                            <Input
                              type="password"
                              placeholder="Enter your password"
                              {...field}
                              data-testid="input-password"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <Button
                      type="submit"
                      size="lg"
                      className="w-full"
                      disabled={isSubmitting}
                      data-testid="button-login"
                    >
                      {isSubmitting ? (
                        <>
                          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                          Signing in...
                        </>
                      ) : (
                        "Sign In"
                      )}
                    </Button>

                    {/* Footer Links */}
                    <div className="pt-6 space-y-4 text-center border-t">
                      <p className="text-muted-foreground">
                        Don't have an account?{" "}
                        <Link
                          href="/register"
                          className="text-primary hover:underline font-semibold"
                          data-testid="link-to-register"
                        >
                          Create one now
                        </Link>
                      </p>
                      <Button
                        variant="ghost"
                        className="w-full"
                        data-testid="link-guest"
                        onClick={() => navigate("/onboarding")}
                      >
                        Continue as Guest
                      </Button>
                    </div>
                  </form>
                </Form>
              </>
            )}
          </CardContent>
        </Card>

        {/* Trust Badge */}
        <p className="mt-8 text-sm text-muted-foreground">
          Secure login • Your data is protected
        </p>
      </div>
    </div>
  );
}
