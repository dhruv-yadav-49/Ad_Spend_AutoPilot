export const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

let inMemoryToken = null;
let refreshPromise = null;

export function setAccessToken(token) {
  inMemoryToken = token;
}

export async function apiFetch(url, options = {}) {
  const headers = { ...options.headers };
  
  if (inMemoryToken) {
    headers["Authorization"] = `Bearer ${inMemoryToken}`;
  }

  // Include credentials for endpoints that need cookies (like /auth/refresh or /auth/logout)
  // Actually, for all apiFetch we can omit, EXCEPT refresh which is handled below.
  // Wait, let's just make it standard for API fetch if needed, but not strictly required unless it's refresh.

  let res = await fetch(API + url, { ...options, headers });

  if (res.status === 401 && !url.includes("/auth/login") && !url.includes("/auth/signup") && !url.includes("/auth/refresh")) {
    if (!refreshPromise) {
      refreshPromise = fetch(API + "/auth/refresh", {
        method: "POST",
        credentials: "include" // REQUIRED to send HttpOnly refresh cookie
      }).then(async (refreshRes) => {
        refreshPromise = null;
        if (refreshRes.ok) {
          const data = await refreshRes.json();
          inMemoryToken = data.access_token;
          return data.access_token;
        } else {
          inMemoryToken = null;
          window.dispatchEvent(new Event("auth_logout"));
          return null;
        }
      });
    }

    const newToken = await refreshPromise;
    
    if (newToken) {
      headers["Authorization"] = `Bearer ${newToken}`;
      res = await fetch(API + url, { ...options, headers });
    }
  }

  return res;
}
