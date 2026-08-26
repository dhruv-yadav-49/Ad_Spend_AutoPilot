import React, { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function Signup() {
  const { signup, user } = useAuth();
  const [mode, setMode] = useState("create"); // "create" or "join"
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (user) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    
    const payload = {
      name,
      email,
      password,
      organization_name: mode === "create" ? organizationName : null,
      invite_code: mode === "join" ? inviteCode : null
    };

    const res = await signup(payload);
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
        <h2>Create your account</h2>
        
        {error && <div className="notice danger">{error}</div>}
        
        <div style={{display: 'flex', gap: '1rem', marginBottom: '1.5rem'}}>
          <button 
            type="button"
            className={mode === "create" ? "" : "outline"} 
            onClick={() => setMode("create")}
            style={{flex: 1}}
          >
            Create Organization
          </button>
          <button 
            type="button"
            className={mode === "join" ? "" : "outline"} 
            onClick={() => setMode("join")}
            style={{flex: 1}}
          >
            Join Organization
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Full Name</label>
            <input required value={name} onChange={e => setName(e.target.value)} placeholder="Jane Doe" />
          </div>
          
          <div className="form-group">
            <label>Email</label>
            <input type="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="you@company.com" />
          </div>
          
          <div className="form-group">
            <label>Password</label>
            <input type="password" required value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" />
          </div>

          {mode === "create" ? (
            <div className="form-group">
              <label>Organization Name</label>
              <input required value={organizationName} onChange={e => setOrganizationName(e.target.value)} placeholder="Acme Corp" />
            </div>
          ) : (
            <div className="form-group">
              <label>Invite Code</label>
              <input required value={inviteCode} onChange={e => setInviteCode(e.target.value)} placeholder="Enter 16-character code" />
            </div>
          )}
          
          <button type="submit" disabled={loading} style={{width: '100%', marginTop: '1rem'}}>
            {loading ? "Creating account..." : (mode === "create" ? "Create Account" : "Join Organization")}
          </button>
        </form>
        
        <p style={{textAlign: 'center', marginTop: '1.5rem', color: '#94a3b8'}}>
          Already have an account? <Link to="/login" className="link">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
