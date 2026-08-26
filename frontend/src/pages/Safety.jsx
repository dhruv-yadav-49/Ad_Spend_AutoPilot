import React, { useState } from "react";
import { apiFetch } from "../api/apiFetch";

export default function Safety() {
  const [t, setT] = useState("");
  const [r, setR] = useState(null);
  
  const review = async () => {
    const res = await apiFetch("/brand-safety/review", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: t })
    });
    setR(await res.json());
  };
  
  return (
    <>
      <header>
        <div>
          <h1>Brand Safety</h1>
          <p>Run copy through policy and risk checks before publishing.</p>
        </div>
      </header>
      <section className="card">
        <textarea rows="8" placeholder="Paste ad copy here…" value={t} onChange={e => setT(e.target.value)} />
        <button onClick={review}>Review Copy</button>
        {r && (
          <div className={"result " + (r.safe ? "safe" : "unsafe")}>
            <h3>{r.recommendation}</h3>
            <p>{r.safe ? "No flagged terms found." : "Flags: " + r.flags.join(", ")}</p>
          </div>
        )}
      </section>
    </>
  );
}
