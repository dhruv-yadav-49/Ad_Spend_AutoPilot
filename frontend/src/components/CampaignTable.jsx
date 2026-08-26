import React, { useState, useEffect } from "react";
import { useAuth } from "../auth/AuthContext";
import { Pause, Play } from "lucide-react";
import { proposeMutation, executeMutation } from "../api/mutations";

export function CampaignTable({ rows, onActionTriggered }) {
  const { user } = useAuth();
  const [items, setItems] = useState(rows);
  const [loadingId, setLoadingId] = useState(null);

  useEffect(() => setItems(rows), [rows]);

  const action = async (c, newStatus) => {
    setLoadingId(c.id);
    try {
      // 1. Propose mutation
      const res = await proposeMutation(
        c.platform,
        c.platform_account_id,
        c.platform_campaign_id,
        newStatus === "paused" ? "pause" : "resume",
        {}
      );
      
      // 2. Based on response status, execute or wait
      if (res.status === "approved") {
        await executeMutation(res.approval_id);
        // Refresh items or call parent callback
        if (onActionTriggered) onActionTriggered();
      } else {
        alert("Action proposed and is pending manager approval.");
        if (onActionTriggered) onActionTriggered();
      }
    } catch (e) {
      alert("Failed to perform action");
      console.error(e);
    } finally {
      setLoadingId(null);
    }
  };

  return (
    <div className="table">
      {items.map(c => (
        <div className="tr" key={c.id}>
          <div>
            <b>{c.name}</b>
            <small>{c.platform === "google" ? "Google Ads" : "Meta Ads"}</small>
          </div>
          <b className={c.status === "ACTIVE" ? "green" : ""}>{c.status}</b>
          <span>{/* Metrics would go here if we had them in this list */}</span>
          
          <button 
            className="icon" 
            onClick={() => action(c, c.status === "ACTIVE" ? "paused" : "active")}
            disabled={loadingId === c.id}
          >
            {loadingId === c.id ? (
              <span className="spinner">...</span>
            ) : c.status === "ACTIVE" ? (
              <Pause size={16} />
            ) : (
              <Play size={16} />
            )}
          </button>
        </div>
      ))}
    </div>
  );
}
