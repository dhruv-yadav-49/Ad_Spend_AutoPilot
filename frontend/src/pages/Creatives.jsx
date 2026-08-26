import React, { useState, useEffect } from "react";
import { apiFetch } from "../api/apiFetch";

export default function Creatives() {
  const [c, setC] = useState([]);
  const [b, setB] = useState(null);
  
  useEffect(() => {
    apiFetch("/campaigns").then(r => r.json()).then(setC);
  }, []);
  
  const gen = async (id) => {
    const res = await apiFetch("/creative/brief", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ campaign_id: id, objective: "Increase conversions" })
    });
    setB(await res.json());
  };
  
  return (
    <>
      <header>
        <div>
          <h1>Creative Intelligence</h1>
          <p>Turn winning messages into the next experiment.</p>
        </div>
      </header>
      <div className="grid three">
        {c.slice(0, 3).map(x => (
          <section className="card creative" key={x.id}>
            <div className="creative-art"></div>
            <h3>{x.name}</h3>
            <span className="badge">ROAS {x.roas}x</span>
            <button onClick={() => gen(x.id)}>Generate AI Brief</button>
          </section>
        ))}
      </div>
      {b && (
        <section className="card result">
          <h2>Generated Creative Brief</h2>
          <h3>{b.campaign}</h3>
          <p>{b.brief}</p>
          <b>Recommended message:</b>
          <p>{b.recommended_message}</p>
          <ul>
            {b.tests.map(x => <li key={x}>{x}</li>)}
          </ul>
        </section>
      )}
    </>
  );
}
