import { apiFetch } from "./apiFetch";

export const getUnifiedCampaigns = () => 
  apiFetch("/platforms/unified/campaigns").then(res => res.json());

export const getUnifiedMetrics = (startDate, endDate) => 
  apiFetch(`/platforms/unified/metrics?start_date=${startDate}&end_date=${endDate}`).then(res => res.json());

export const getDashboardMock = () => 
  apiFetch("/dashboard").then(res => res.json());
