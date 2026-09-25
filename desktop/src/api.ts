import { invoke } from "@tauri-apps/api/core";

type Connection = { base: string; token: string };
let connection: Promise<Connection> | null = null;

function getConnection(): Promise<Connection> {
  if (!connection) {
    connection = (async () => {
      if ("__TAURI_INTERNALS__" in window) {
        const info = await invoke<{ port: number; token: string }>("backend_info");
        const resolved = { base: `http://127.0.0.1:${info.port}`, token: info.token };
        for (let attempt = 0; attempt < 300; attempt++) {
          try {
            const health = await fetch(`${resolved.base}/api/health`, { headers: { "X-FilingLens-Token": resolved.token } });
            if (health.ok) return resolved;
          } catch { /* bundled service is still starting */ }
          await new Promise(done => setTimeout(done, 500));
        }
        throw new Error("The FilingLens local service did not start. Reopen the app, or use the previous Streamlit version while troubleshooting.");
      }
      return { base: "", token: "" };
    })();
  }
  return connection;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { base, token } = await getConnection();
  const headers = new Headers(init.headers);
  if (token) headers.set("X-FilingLens-Token", token);
  if (init.body) headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(base + path, { ...init, headers });
  } catch {
    throw new Error("FilingLens could not reach its local service. Try reopening the app.");
  }
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try { message = (await response.json()).detail || message; } catch { /* malformed error */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function post<T>(path: string, body: object): Promise<T> {
  return api<T>(path, { method: "POST", body: JSON.stringify(body) });
}
