import React, { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { CampaignTable } from "../components/CampaignTable";
import { getUnifiedCampaigns } from "../api/reporting";

export default function Campaigns() {
  const { user } = useAuth();
  const [rows, setRows] = useState([]);
  
  const load = () => {
    getUnifiedCampaigns().then(res => setRows(res.data || []));
  };
  
  useEffect(() => { load(); }, []);
  
  return (
    <>
      <header>
        <div>
          <h1>Campaigns</h1>
          <p>Manage cross-channel campaigns and live guardrails.</p>
        </div>
      </header>
      <div className="grid">
        <section className="card">
          <h2>Live Campaign List</h2>
          <CampaignTable rows={rows} onActionTriggered={load} />
        </section>
      </div>
    </>
  );
}
