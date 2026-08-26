import React, { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function Login() {
  const { login, user } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (user) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    const res = await login(email, password);
    if (!res.success) {
      setError(res.error);
    }
    setLoading(false);
  };

  return (
    <div className="auth-container">
      <div className="card auth-card">
        <div className="brand" style={{justifyContent: 'center', marginBottom: '2rem'}}>
          Ad Spend <b>Autopilot</b>
        </div>
        <h2>Sign in to your account</h2>
        
        {error && <div className="notice danger">{error}</div>}
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Email</label>
            <input 
              type="email" 
              required 
              value={email} 
              onChange={e => setEmail(e.target.value)} 
              placeholder="you@company.com" 
            />
          </div>
          
          <div className="form-group">
            <label>Password</label>
            <input 
              type="password" 
              required 
              value={password} 
              onChange={e => setPassword(e.target.value)} 
              placeholder="••••••••" 
            />
          </div>
          
          <button type="submit" disabled={loading} style={{width: '100%', marginTop: '1rem'}}>
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
        
        <p style={{textAlign: 'center', marginTop: '1.5rem', color: '#94a3b8'}}>
          Don't have an account? <Link to="/signup" className="link">Sign up</Link>
        </p>
      </div>
    </div>
  );
}
