import React, { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { getUnifiedCampaigns } from "../api/reporting";
import { proposeMutation, executeMutation } from "../api/mutations";

export default function Budget() {
  const { user } = useAuth();
  const [campaigns, setCampaigns] = useState([]);
  const [message, setMessage] = useState("");
  
  useEffect(() => {
    getUnifiedCampaigns().then(res => setCampaigns(res.data || []));
  }, []);
  
  const change = async (c) => {
    let n = Number(prompt(`New daily budget (USD) for ${c.name}`, "500"));
    if (!n) return;
    
    try {
      const res = await proposeMutation(
        c.platform, 
        c.platform_account_id, 
        c.platform_campaign_id, 
        "update_budget", 
        { new_daily_budget: n }
      );
      
      if (res.status === "approved") {
        await executeMutation(res.approval_id);
        setMessage(`Budget changed automatically within guardrails for ${c.name}.`);
      } else {
        setMessage(`Mutation proposed. Status: PENDING APPROVAL. Waiting for Manager approval.`);
      }
    } catch (e) {
      console.error(e);
      setMessage("Failed to propose/execute budget change.");
    }
  };
  
  return (
    <>
      <header>
        <div>
          <h1>Budget Automation</h1>
          <p>AI acts inside safe limits; larger changes require approval.</p>
        </div>
      </header>
      {message && <div className="notice" style={{background:'#dbeafe', color:'#1e40af'}}>{message}</div>}
      
      <section className="card">
        <h2>Budget Guardrails</h2>
        {campaigns.map(x => (
          <div className="tr" key={x.id}>
            <div>
              <b>{x.name}</b>
              <small>{x.platform === 'google' ? 'Google Ads' : 'Meta Ads'}</small>
            </div>
            <b>Live</b>
            <button onClick={() => change(x)}>
              {user.role === 'manager' ? "Optimize Budget" : "Suggest Optimization"}
            </button>
          </div>
        ))}
        {user.role === 'analyst' && (
          <p style={{fontSize: '0.8rem', color: '#94a3b8', marginTop: '1rem'}}>
            * Your suggestion will require manager approval.
          </p>
        )}
      </section>
    </>
  );
}
