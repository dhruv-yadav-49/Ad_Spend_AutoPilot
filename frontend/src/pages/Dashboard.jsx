import React, { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, PieChart, Pie, Cell, Legend } from "recharts";
import { Sparkles, Activity } from "lucide-react";
import { Card } from "../components/Card";
import { CampaignTable } from "../components/CampaignTable";
import { getUnifiedCampaigns, getUnifiedMetrics, getDashboardMock } from "../api/reporting";

export default function Dashboard() {
  const { user } = useAuth();
  const [kpis, setKpis] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [platforms, setPlatforms] = useState({});
  const [recentEvents, setRecentEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      setLoading(true);
      // Fetch real unified data
      const campRes = await getUnifiedCampaigns();
      setCampaigns(campRes.data || []);
      setPlatforms(campRes.platforms || {});

      // Calculate dates for past 30 days
      const end = new Date().toISOString().split('T')[0];
      const start = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
      const metRes = await getUnifiedMetrics(start, end);

      // Aggregate metrics
      let totalSpend = 0;
      let totalConversions = 0;
      let channelSpend = [];

      (metRes.data || []).forEach(m => {
        const spend = m.cost_micros / 1000000;
        totalSpend += spend;
        totalConversions += m.conversions;
        channelSpend.push({ channel: m.platform, spend });
      });

      setKpis({
        total_spend: totalSpend,
        conversions: totalConversions,
        cpa: totalConversions > 0 ? (totalSpend / totalConversions).toFixed(2) : 0,
        roas: 0 // Cannot reliably calculate without revenue
      });

      // Get mock events just for visual filler in dashboard
      const mock = await getDashboardMock();
      setRecentEvents(mock.recent_events || []);
      
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  if (loading) return <div className="loading">Fetching live performance data...</div>;

  return (
    <>
      <header>
        <div>
          <h1>Dashboard</h1>
          <p>Real-time view of ad performance and autonomous spend.</p>
        </div>
      </header>
      
      <div className="platform-status-bar">
        {Object.entries(platforms).map(([plat, info]) => (
          <span key={plat} className={`status-badge ${info.status}`}>
            {plat === 'google' ? 'Google Ads' : 'Meta Ads'}: {info.status.replace('_', ' ')}
          </span>
        ))}
      </div>

      <div className="grid kpis">
        <Card title="Total Spend (30d)" value={`$${kpis.total_spend.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}`} delta="Live" />
        <Card title="Conversions" value={kpis.conversions.toLocaleString()} delta="Live" />
        <Card title="Avg CPA" value={`$${kpis.cpa}`} delta="Live" />
        <Card title="Active Campaigns" value={campaigns.filter(c => c.status === 'ACTIVE' || c.status === 'ENABLED').length} delta="Live" />
      </div>
      
      <div className="grid two">
        <section className="card">
          <h2>Top Campaigns</h2>
          <CampaignTable rows={campaigns} onActionTriggered={loadData} />
        </section>
        
        <section className="card">
          <h2>Autopilot Activity</h2>
          {recentEvents.map((e, i) => (
            <div className="event" key={i}>
              <Sparkles size={16} />
              <div>
                <b>{e.action}</b>
                <small>{e.campaign}: {e.reason}</small>
              </div>
            </div>
          ))}
        </section>
      </div>
    </>
  );
}
