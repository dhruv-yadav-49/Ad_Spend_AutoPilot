import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, NavLink, Routes, Route } from "react-router-dom";
import { LayoutDashboard, Megaphone, Palette, Wallet, FileBarChart, CheckSquare, ShieldCheck, Settings, Bot } from "lucide-react";
import "./styles.css";

import { AuthProvider, useAuth } from "./auth/AuthContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { Login } from "./pages/Login";
import { Signup } from "./pages/Signup";

import Dashboard from "./pages/Dashboard";
import Campaigns from "./pages/Campaigns";
import Creatives from "./pages/Creatives";
import Budget from "./pages/Budget";
import Attribution from "./pages/Attribution";
import Approvals from "./pages/Approvals";
import Safety from "./pages/Safety";
import Integrations from "./pages/Integrations";

const nav = [
  ["/", "Dashboard", LayoutDashboard],
  ["/campaigns", "Campaigns", Megaphone],
  ["/creatives", "Creatives", Palette],
  ["/budget", "Budget Automation", Wallet],
  ["/attribution", "Attribution", FileBarChart],
  ["/approvals", "Approvals", CheckSquare],
  ["/safety", "Brand Safety", ShieldCheck],
  ["/settings/integrations", "Settings", Settings]
];

function Layout() {
  const { user, logout } = useAuth();
  return (
    <div className="app">
      <aside>
        <div className="brand"><Bot />Ad Spend <b>Autopilot</b></div>
        <div className="profile">
          <strong>{user.name}</strong><br />
          <small>{user.role === 'manager' ? 'Manager' : 'Analyst'} · {user.organization_name}</small><br />
          <button className="profile-action" onClick={logout}>Sign Out</button>
        </div>
        {nav.map(([to, label, Icon]) => (
          <NavLink key={to} to={to} className={({ isActive }) => isActive ? "active" : ""}>
            <Icon size={18} />{label}
          </NavLink>
        ))}
        <div className="sidebar-bottom">● All systems operational</div>
      </aside>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/campaigns" element={<Campaigns />} />
          <Route path="/creatives" element={<Creatives />} />
          <Route path="/budget" element={<Budget />} />
          <Route path="/attribution" element={<Attribution />} />
          <Route path="/approvals" element={<Approvals />} />
          <Route path="/safety" element={<Safety />} />
          <Route path="/settings/integrations" element={<Integrations />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/*" element={<Layout />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")).render(<App />);
