import React, { useState, useEffect } from "react";
import { apiFetch } from "../api/apiFetch";
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";

export default function Attribution() {
  const [d, setD] = useState([]);
  useEffect(() => {
    apiFetch("/reports/attribution").then(r => r.json()).then(setD);
  }, []);
  return (
    <>
      <header>
        <div>
          <h1>Attribution Report</h1>
          <p>Weekly cross-channel performance summary.</p>
        </div>
        <button>Export CSV</button>
      </header>
      <section className="card chart">
        <ResponsiveContainer width="100%" height={360}>
          <BarChart data={d}>
            <XAxis dataKey="channel" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="conversions" fill="#6d5dfc" />
            <Bar dataKey="revenue" fill="#2bb673" />
          </BarChart>
        </ResponsiveContainer>
      </section>
    </>
  );
}
