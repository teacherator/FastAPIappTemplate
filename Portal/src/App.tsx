import { useState } from "react";
import { Redirect, Route, Router, Switch } from "wouter";
import Login from "./pages/Login";
import Home from "./pages/Home";
import Register from "./pages/Register";

export default function App() {
  const [email, setEmail] = useState(() => localStorage.getItem("email") ?? "");

  const handleLogout = () => {
    localStorage.removeItem("email");
    setEmail("");
    window.location.href = "/portal/";
  };

  return (
    <div className="min-h-screen">
      {email ? (
        <Home email={email} onLogout={handleLogout} />
      ) : (
        <Router base="/portal">
          <Switch>
            <Route path="/" component={Login} />
            <Route path="/register" component={Register} />
            <Route>
              <Redirect to="/" />
            </Route>
          </Switch>
        </Router>
      )}
    </div>
  );
}
