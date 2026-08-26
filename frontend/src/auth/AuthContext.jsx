import React, { createContext, useContext, useState, useEffect } from "react";
import { apiFetch, setAccessToken, API } from "../api/apiFetch";

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadUser = async () => {
    try {
      const res = await apiFetch("/auth/me");
      if (res.ok) {
        const data = await res.json();
        setUser(data);
      } else {
        setUser(null);
      }
    } catch (e) {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUser();

    const handleLogoutEvent = () => {
      setUser(null);
      setAccessToken(null);
    };

    window.addEventListener("auth_logout", handleLogoutEvent);
    return () => window.removeEventListener("auth_logout", handleLogoutEvent);
  }, []);

  const login = async (email, password) => {
    const res = await fetch(API + "/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
      credentials: "omit" // no credentials needed for login, it sets the cookie itself
    });
    
    if (res.ok) {
      const data = await res.json();
      setAccessToken(data.access_token);
      await loadUser();
      return { success: true };
    }
    const err = await res.json();
    return { success: false, error: err.detail || "Login failed" };
  };

  const signup = async (payload) => {
    const res = await fetch(API + "/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    
    if (res.ok) {
      // Auto login after signup
      return login(payload.email, payload.password);
    }
    const err = await res.json();
    return { success: false, error: err.detail || "Signup failed" };
  };

  const logout = async () => {
    await fetch(API + "/auth/logout", {
      method: "POST",
      credentials: "include" // need to send cookie to clear it
    });
    setUser(null);
    setAccessToken(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
