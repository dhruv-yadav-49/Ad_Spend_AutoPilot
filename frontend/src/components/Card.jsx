import React from "react";

export const Card = ({ title, value, delta }) => (
  <div className="card kpi">
    <span>{title}</span>
    <strong>{value}</strong>
    <em>{delta}</em>
  </div>
);
