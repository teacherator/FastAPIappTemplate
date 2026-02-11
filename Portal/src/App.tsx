import { useState } from "react";
import Login from "./pages/Login";
import Home from "./pages/Home";

export default function App() {
  const [email, setEmail] = useState(() => localStorage.getItem("email") ?? "");

  const handleLogout = () => {
    localStorage.removeItem("email");
    setEmail("");
    window.location.href = "/portal/";
  };

  return (
    <div className="min-h-screen">
      {email ? <Home email={email} onLogout={handleLogout} /> : <Login />}
    </div>
  );
}
