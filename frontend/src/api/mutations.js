import { apiFetch } from "./apiFetch";

export const proposeMutation = async (platform, platform_account_id, platform_campaign_id, action, action_payload) => {
  return apiFetch("/platforms/mutations/propose", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      platform,
      platform_account_id,
      platform_campaign_id,
      action,
      action_payload
    })
  }).then(res => res.json());
};

export const approveMutation = async (approval_id) => {
  return apiFetch(`/platforms/mutations/${approval_id}/approve`, { method: "POST" }).then(res => res.json());
};

export const rejectMutation = async (approval_id) => {
  return apiFetch(`/platforms/mutations/${approval_id}/reject`, { method: "POST" }).then(res => res.json());
};

export const executeMutation = async (approval_id) => {
  return apiFetch(`/platforms/mutations/${approval_id}/execute`, { method: "POST" }).then(res => res.json());
};

export const retryMutation = async (approval_id) => {
  return apiFetch(`/platforms/mutations/${approval_id}/retry`, { method: "POST" }).then(res => res.json());
};

export const getApprovals = async () => {
  return apiFetch("/approvals").then(res => res.json());
};
