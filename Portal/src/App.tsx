import { useEffect, useState } from "react";
import { Redirect, Route, Router, Switch } from "wouter";
import Login from "./pages/Login";
import Home from "./pages/Home";
import Register from "./pages/Register";

type SessionUser = {
  email: string;
  type: string;
};

export default function App() {
  const [sessionUser, setSessionUser] = useState<SessionUser | null>(null);
  const [isLoadingSession, setIsLoadingSession] = useState(true);

  useEffect(() => {
    const loadSession = async () => {
      try {
        const response = await fetch("/me", { credentials: "include" });
        if (!response.ok) {
          localStorage.removeItem("email");
          setSessionUser(null);
          return;
        }

        const me = (await response.json()) as SessionUser;
        localStorage.setItem("email", me.email);
        setSessionUser(me);
      } catch {
        localStorage.removeItem("email");
        setSessionUser(null);
      } finally {
        setIsLoadingSession(false);
      }
    };

    loadSession();
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("email");
    setSessionUser(null);
    window.location.href = "/portal/";
  };

  return (
    <div className="min-h-screen">
      <Router base="/portal">
        <Switch>
          <Route path="/">
            {isLoadingSession ? null : sessionUser ? (
              <Home email={sessionUser.email} userType={sessionUser.type} onLogout={handleLogout} />
            ) : (
              <Login />
            )}
          </Route>
          <Route path="/register" component={Register} />
          <Route>
            <Redirect to="/" />
          </Route>
        </Switch>
      </Router>
    </div>
  );
}
