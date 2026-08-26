import React, { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { apiFetch, API } from "../api/apiFetch";

export default function Integrations() {
  const { user } = useAuth();
  const [connections, setConnections] = useState([]);
  const [errorMsg, setErrorMsg] = useState("");
  
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("error")) setErrorMsg(`OAuth failed: ${params.get("error")}`);
    loadConnections();
  }, []);
  
  const loadConnections = () => {
    apiFetch("/platforms/connections")
      .then(res => res.json())
      .then(data => setConnections(data))
      .catch(e => console.error(e));
  };
  
  const connect = (platform) => {
    window.location.href = `${API}/platforms/${platform}/connect?token=${localStorage.getItem('access_token')}`;
  };
  
  const disconnect = async (platform) => {
    try {
      await apiFetch(`/platforms/${platform}/disconnect`, { method: "DELETE" });
      loadConnections();
    } catch (e) {
      console.error(e);
    }
  };
  
  const renderPlatform = (platformId, platformName) => {
    const conn = connections.find(c => c.platform === platformId && c.status === 'active');
    return (
      <div className="tr" key={platformId}>
        <div>
          <b>{platformName}</b>
          <small>{conn ? (conn.external_account_name || "Connected") : "Not connected"}</small>
        </div>
        {conn ? (
          <div>
            <span className="badge" style={{background: 'rgba(34,197,94,0.1)', color: '#16a34a'}}>🟢 Connected</span>
            <button className="danger" onClick={() => disconnect(platformId)} style={{marginLeft: '1rem'}}>Disconnect</button>
          </div>
        ) : (
          <button onClick={() => connect(platformId)}>Connect {platformName}</button>
        )}
      </div>
    );
  };
  
  return (
    <>
      <header>
        <div>
          <h1>Integrations</h1>
          <p>Connect and manage external ad platforms.</p>
        </div>
      </header>
      {errorMsg && <div className="notice" style={{background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444'}}>{errorMsg}</div>}
      <section className="card">
        <h2>Ad Platforms</h2>
        <div className="table">
          {renderPlatform("google", "Google Ads")}
          {renderPlatform("meta", "Meta Ads")}
        </div>
      </section>
    </>
  );
}
