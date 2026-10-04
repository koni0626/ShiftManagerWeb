export type Row = {
  id: string;
  version: number;
  name: string;
  [key: string]: any;
};
export type Actor = {
  id: string;
  name: string;
  role: "system_admin" | "owner" | "member";
  scope_id: string | null;
  staff_id: string | null;
};
export type Issue = {
  visit_ids: string[];
  message: string;
  level: "error" | "warning";
};
export type Workspace = {
  scope: Row;
  company: Row;
  branches: Row[];
  staff: Row[];
  services: Row[];
  clients: Row[];
  visits: Row[];
  duties: Row[];
  memberships: Row[];
  windows: Row[];
  submissions: Row[];
  pay_terms: Row[];
  history: Row[];
  issues: Issue[];
  geocoding_enabled: boolean;
};
export async function api<T = any>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const csrf =
    document.cookie
      .split("; ")
      .find((x) => x.startsWith("atelier_csrf="))
      ?.split("=")[1] || "";
  const res = await fetch("/api/v1" + path, {
    method,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": decodeURIComponent(csrf),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok)
    throw new Error(
      [
        data.message || "通信できませんでした",
        ...(Array.isArray(data.details)
          ? data.details.map((x: any) => x.message)
          : []),
      ].join("\n"),
    );
  return data;
}
export const dayText = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export const today = () => dayText(new Date());
export const addDays = (d: string, n: number) => {
  const x = new Date(d + "T12:00:00");
  x.setDate(x.getDate() + n);
  return dayText(x);
};
export const shortDate = (d: string) =>
  new Date(d + "T12:00:00").toLocaleDateString("ja-JP", {
    month: "numeric",
    day: "numeric",
    weekday: "short",
  });
export const clock = (m: number) =>
  `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
export const min = (s: string) =>
  Number(s.slice(0, 2)) * 60 + Number(s.slice(3, 5));
export const statuses: Record<string, string> = {
  draft: "仮予定",
  confirmed: "確定",
  done: "完了",
  cancelled: "中止",
  readjusting: "再調整中",
};
