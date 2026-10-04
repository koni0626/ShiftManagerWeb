import { useState } from "react";
import {
  CalendarDays,
  Clock3,
  TriangleAlert,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  Plus,
} from "lucide-react";
import {
  api,
  addDays,
  today,
  shortDate,
  min,
  clock,
  statuses,
  type Workspace,
  type Row,
} from "./api";
import { ErrorBox } from "./components";
export default function Schedule({
  data,
  scope,
  branch,
  onEdit,
  onNew,
  reload,
}: {
  data: Workspace;
  scope: string;
  branch: string;
  onEdit: (v: Row) => void;
  onNew: (values?: Record<string, unknown>) => void;
  reload: () => Promise<void>;
}) {
  const [date, setDate] = useState(today()),
    [mode, setMode] = useState("week"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [over, setOver] = useState("");
  const visits = data.visits.filter((v) => !branch || v.branch_id === branch);
  const monthVisits = visits.filter((v) => v.date.startsWith(date.slice(0, 7)));
  const monday = addDays(
    date,
    -((new Date(date + "T12:00:00").getDay() + 6) % 7),
  );
  const days =
    mode === "week"
      ? Array.from({ length: 7 }, (_, i) => addDays(monday, i))
      : [date];
  const people = [
    ...data.staff.filter(
      (p) =>
        (p.active && (!branch || p.branch_ids.includes(branch))) ||
        visits.some((v) => days.includes(v.date) && v.staff_ids.includes(p.id)),
    ),
    { id: "", name: "担当未定", job: "割当待ち", version: 1 } as Row,
  ];
  const lookup = (list: Row[], id: string) => list.find((x) => x.id === id);
  const dayVisits = visits.filter((v) => v.date === date);
  const firstMinute = Math.min(
    480,
    ...dayVisits.map((v) => Math.floor(min(v.start) / 60) * 60),
  );
  const lastMinute = Math.max(
    1200,
    ...dayVisits.map((v) => Math.ceil((min(v.start) + v.duration) / 60) * 60),
  );
  const spanMinutes = lastMinute - firstMinute;
  const hourCount = spanMinutes / 60;
  async function drop(
    e: React.DragEvent,
    staff: string,
    day: string,
    start?: string,
  ) {
    e.preventDefault();
    setOver("");
    if (busy) return;
    try {
      const item = JSON.parse(
        e.dataTransfer.getData("application/atelier-visit"),
      );
      setBusy(true);
      await api(`/scopes/${scope}/visits/${item.id}/position`, "PATCH", {
        expected_version: item.version,
        target_date: day,
        target_start: start,
        source_staff_id: item.source,
        target_staff_id: staff,
      });
      await reload();
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function card(v: Row, staff: string, timeline = false, lane = 0) {
    return (
      <button
        key={v.id}
        data-visit-id={v.id}
        type="button"
        className={"visit-card " + v.status}
        style={
          timeline
            ? {
                left: `${((min(v.start) - firstMinute) / spanMinutes) * 100}%`,
                width: `${Math.min(Math.max((v.duration / spanMinutes) * 100, 8), ((lastMinute - min(v.start)) / spanMinutes) * 100)}%`,
                top: `${12 + lane * 155}px`,
              }
            : undefined
        }
        draggable={v.status === "draft" && !busy}
        onDragStart={(e) => {
          e.dataTransfer.setData(
            "application/atelier-visit",
            JSON.stringify({ id: v.id, version: v.version, source: staff }),
          );
          e.dataTransfer.effectAllowed = "move";
        }}
        onClick={() => onEdit(v)}
      >
        <small>
          {v.start}–{clock(min(v.start) + v.duration)}
        </small>
        <strong>{lookup(data.clients, v.client_id)?.label}</strong>
        <span>{lookup(data.services, v.service_id)?.name}</span>
        {!branch && (
          <span className="branch-label">
            {lookup(data.branches, v.branch_id)?.name}
          </span>
        )}
        <small className="visit-status">{statuses[v.status]}</small>
      </button>
    );
  }
  return (
    <>
      <div className="metrics">
        {[
          {
            label: "今月の訪問予定",
            value: monthVisits.filter((v) => v.status !== "cancelled").length,
            icon: <CalendarDays />,
            tone: "sage",
          },
          {
            label: "担当者が未調整",
            value: monthVisits.filter(
              (v) => v.staff_ids.length < v.people && v.status !== "cancelled",
            ).length,
            icon: <Clock3 />,
            tone: "sand",
          },
          {
            label: "確認が必要",
            value: data.issues.filter(
              (i) =>
                i.level === "error" &&
                i.visit_ids.some((id) => monthVisits.some((v) => v.id === id)),
            ).length,
            icon: <TriangleAlert />,
            tone: "peach",
          },
          {
            label: "訪問が完了",
            value: monthVisits.filter((v) => v.status === "done").length,
            icon: <CheckCheck />,
            tone: "blue",
          },
        ].map((x) => (
          <div key={x.label} className={"metric " + x.tone}>
            <span>
              {x.icon}
              {x.label}
            </span>
            <strong>
              {x.value}
              <small>件</small>
            </strong>
          </div>
        ))}
      </div>
      <div className="toolbar">
        <div className="segment">
          <button
            className={mode === "day" ? "active" : ""}
            onClick={() => setMode("day")}
          >
            日
          </button>
          <button
            className={mode === "week" ? "active" : ""}
            onClick={() => setMode("week")}
          >
            週
          </button>
        </div>
        <span className="view-label">担当者別</span>
        <button
          className="icon-button"
          aria-label="前の期間"
          onClick={() => setDate(addDays(date, mode === "week" ? -7 : -1))}
        >
          <ChevronLeft size={18} />
        </button>
        <input
          type="date"
          aria-label="表示日"
          value={date}
          onChange={(e) => e.target.value && setDate(e.target.value)}
        />
        <button
          className="icon-button"
          aria-label="次の期間"
          onClick={() => setDate(addDays(date, mode === "week" ? 7 : 1))}
        >
          <ChevronRight size={18} />
        </button>
        <button className="button subtle" onClick={() => setDate(today())}>
          今日
        </button>
        <button
          className="button primary push"
          onClick={() =>
            onNew({ date, branch_id: branch || data.branches[0]?.id })
          }
        >
          <Plus size={17} />
          訪問を追加
        </button>
      </div>
      <p className="hint">
        仮予定のカードをドラッグすると、
        {mode === "week" ? "日付・担当者" : "時間・担当者"}
        を変更できます。カードをクリックして詳しく編集できます。
      </p>
      <ErrorBox message={error} />
      <div
        className={"panel schedule-scroll " + (busy ? "saving" : "")}
        aria-busy={busy}
      >
        {mode === "week" ? (
          <table className="week-table">
            <thead>
              <tr>
                <th>担当者</th>
                {days.map((d) => (
                  <th key={d} className={d === today() ? "is-today" : ""}>
                    {shortDate(d)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {people.map((p) => (
                <tr key={p.id}>
                  <th>
                    <strong>{p.name}</strong>
                    <small>{p.job}</small>
                  </th>
                  {days.map((d) => (
                    <td
                      key={d}
                      data-date={d}
                      data-staff-id={p.id}
                      className={over === p.id + d ? "drop-target" : ""}
                      onDragOver={(e) => {
                        e.preventDefault();
                        setOver(p.id + d);
                      }}
                      onDragLeave={() => setOver("")}
                      onDrop={(e) => void drop(e, p.id, d)}
                    >
                      {visits
                        .filter(
                          (v) =>
                            v.date === d &&
                            (p.id
                              ? v.staff_ids.includes(p.id)
                              : !v.staff_ids.length),
                        )
                        .sort((a, b) => a.start.localeCompare(b.start))
                        .map((v) => card(v, p.id))}
                      <button
                        className="add-slot"
                        aria-label={`${p.name} ${d}に追加`}
                        onClick={() =>
                          onNew({
                            date: d,
                            staff_ids: p.id ? [p.id] : [],
                            branch_id:
                              branch ||
                              p.branch_ids?.[0] ||
                              data.branches[0]?.id,
                          })
                        }
                      >
                        <Plus size={15} />
                      </button>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="timeline">
            <div className="time-head">
              <span>担当者</span>
              <div style={{ gridTemplateColumns: `repeat(${hourCount}, 1fr)` }}>
                {Array.from({ length: hourCount }, (_, i) => (
                  <span key={i}>{i + firstMinute / 60}:00</span>
                ))}
              </div>
            </div>
            {people.map((p) => {
              const ends: number[] = [];
              const placements = visits
                .filter(
                  (v) =>
                    v.date === date &&
                    (p.id ? v.staff_ids.includes(p.id) : !v.staff_ids.length),
                )
                .sort((a, b) => a.start.localeCompare(b.start))
                .map((v) => {
                  let lane = ends.findIndex((end) => end <= min(v.start));
                  if (lane < 0) lane = ends.length;
                  ends[lane] =
                    min(v.start) + Math.max(v.duration, spanMinutes * 0.08);
                  return { visit: v, lane };
                });
              return (
                <div className="time-row" key={p.id}>
                  <div className="time-person">
                    <strong>{p.name}</strong>
                    <small>{p.job}</small>
                  </div>
                  <div
                    className={
                      "time-track " + (over === p.id ? "drop-target" : "")
                    }
                    style={{
                      minHeight: Math.max(176, ends.length * 155 + 24),
                      backgroundImage: `repeating-linear-gradient(to right,transparent 0,transparent calc(${100 / hourCount}% - 1px),#e9e7dc calc(${100 / hourCount}% - 1px),#e9e7dc ${100 / hourCount}%)`,
                    }}
                    onDragOver={(e) => {
                      e.preventDefault();
                      setOver(p.id);
                    }}
                    onDragLeave={() => setOver("")}
                    onDrop={(e) => {
                      const box = e.currentTarget.getBoundingClientRect();
                      const start = clock(
                        Math.round(
                          (firstMinute +
                            ((e.clientX - box.left) / box.width) *
                              spanMinutes) /
                            15,
                        ) * 15,
                      );
                      void drop(e, p.id, date, start);
                    }}
                  >
                    {placements.map(({ visit, lane }) =>
                      card(visit, p.id, true, lane),
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
