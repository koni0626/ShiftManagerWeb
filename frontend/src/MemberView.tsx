import { useEffect, useState } from "react";
import { CalendarDays, Clock3, MapPin } from "lucide-react";
import { api, today, shortDate, clock, min, statuses, type Row } from "./api";
import { Empty, ErrorBox, Submit } from "./components";
import MapView from "./MapView";

export function MemberSchedule({ data, page }: { data: any; page: string }) {
  const [date, setDate] = useState(today());
  const visits: Row[] = data.visits
    .filter((v: Row) =>
      page !== "schedule"
        ? v.date === date
        : v.date.slice(0, 7) === date.slice(0, 7),
    )
    .sort((a: Row, b: Row) =>
      (a.date + a.start).localeCompare(b.date + b.start),
    );
  const places = visits
    .filter((v) => v.location)
    .map((v) => ({ id: v.client_id, ...v.location }));
  const clients = [...new Map(places.map((v) => [v.id, v])).values()];
  return (
    <>
      <div className="toolbar">
        <CalendarDays size={19} />
        <input
          aria-label="確認する日"
          type="date"
          value={date}
          onChange={(e) => e.target.value && setDate(e.target.value)}
        />
        <button className="button subtle" onClick={() => setDate(today())}>
          今日
        </button>
        <span className="hint">
          {page === "schedule"
            ? "選択した月の公開済み予定"
            : "公開済みの担当予定"}
        </span>
      </div>
      {page === "map" ? (
        <MapView clients={clients} />
      ) : (
        <>
          {data.duties
            .filter((d: Row) => d.date === date)
            .map((d: Row) => (
              <div className="panel duty-summary" key={d.id}>
                <Clock3 size={20} />
                <strong>{shortDate(d.date)}の勤務</strong>
                <span>{d.off ? "休み" : `${d.start}–${d.end}`}</span>
                {d.break_start && (
                  <small>
                    休憩 {d.break_start}–{d.break_end}
                  </small>
                )}
              </div>
            ))}
          {visits.length === 0 ? (
            <Empty>この期間の公開済み訪問はありません。</Empty>
          ) : (
            <div className="member-visits">
              {visits.map((v) => (
                <article className="panel person-card" key={v.id}>
                  <div className="row between">
                    <span className="eyebrow">{shortDate(v.date)}</span>
                    <span className={"status " + v.status}>
                      {statuses[v.status]}
                    </span>
                  </div>
                  <h2>
                    {v.start}–{clock(min(v.start) + v.duration)}　
                    {v.client_label}
                  </h2>
                  <p>
                    {v.service_name} · {v.branch_name}
                  </p>
                  {v.location && (
                    <>
                      <p className="address-line">
                        <MapPin size={16} />
                        {v.location.address || "住所未登録"}{" "}
                        {v.location.building}
                      </p>
                      <div className="visit-guide">
                        {v.location.guide || "訪問案内は未登録です。"}
                      </div>
                      {v.location.phone && (
                        <a
                          className="button subtle"
                          href={"tel:" + v.location.phone}
                        >
                          {v.location.phone}
                        </a>
                      )}
                      {v.location.address && (
                        <a
                          className="button secondary"
                          href={
                            "https://www.google.com/maps/search/?api=1&query=" +
                            encodeURIComponent(
                              v.location.address + " " + v.location.building,
                            )
                          }
                          target="_blank"
                          rel="noreferrer"
                        >
                          場所を確認
                        </a>
                      )}
                    </>
                  )}
                  {v.status === "readjusting" && (
                    <p className="hint">
                      現在調整中です。直前に公開された内容を表示しています。
                    </p>
                  )}
                </article>
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}

export function MemberRequests({
  data,
  reload,
  requestBase = "/me/requests",
  initialMonth = today().slice(0, 7),
  targetName,
  proxy = false,
  onReturn,
  onEditState,
}: {
  data: any;
  reload: () => Promise<void>;
  requestBase?: string;
  initialMonth?: string;
  targetName?: string;
  proxy?: boolean;
  onReturn?: (row: Row, reason: string) => Promise<void>;
  onEditState?: (state: { dirty: boolean; busy: boolean }) => void;
}) {
  const [month, setMonth] = useState(initialMonth);
  const [reason, setReason] = useState("勤務希望の内容を修正するため");
  const row: Row | undefined = data.submissions.find(
      (x: Row) => x.month === month,
    ),
    window = data.windows.find((x: Row) => x.month === month);
  const [days, setDays] = useState<Record<string, any>>({}),
    [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const closed = Boolean(
    window && window.deadline < today() && row?.status !== "returned",
  );
  useEffect(() => {
    onEditState?.({ dirty, busy });
  }, [dirty, busy, onEditState]);
  useEffect(() => {
    setDays(Object.fromEntries((row?.days || []).map((d: any) => [d.date, d])));
    setDirty(false);
  }, [month, row?.version]);
  const length = new Date(
    Number(month.slice(0, 4)),
    Number(month.slice(5)),
    0,
  ).getDate();
  const dates = Array.from(
    { length },
    (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`,
  );
  const set = (d: string, k: string, value: any) => {
    setDays((x) => ({
      ...x,
      [d]: {
        date: d,
        kind: "",
        start: "09:00",
        end: "18:00",
        note: "",
        ...x[d],
        [k]: value,
      },
    }));
    setDirty(true);
  };
  async function save(action = "save") {
    setBusy(true);
    setError("");
    try {
      if (action === "return" && row && onReturn) {
        await onReturn(row, reason);
      } else {
        await api(
          `${requestBase}/${month}${action === "save" ? "" : "/" + action}`,
          action === "save" ? "PUT" : "POST",
          action === "save"
            ? {
                expected_version: row?.version,
                days: Object.values(days).filter((d) => d.kind),
              }
            : { expected_version: row?.version },
        );
      }
      await reload();
      setDirty(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      {targetName && (
        <p className="notice-box">
          <strong>{targetName}</strong> さんの勤務希望
          {proxy ? "を代理入力しています。" : "を入力しています。"}
        </p>
      )}
      <div className="toolbar">
        <input
          type="month"
          aria-label="希望の対象月"
          value={month}
          disabled={busy}
          onChange={(e) => {
            if (
              e.target.value &&
              (!dirty ||
                globalThis.confirm(
                  "保存していない変更を破棄して、対象月を変更しますか？",
                ))
            ) {
              setMonth(e.target.value);
              setError("");
            }
          }}
        />
        {window && <span>提出期限：{shortDate(window.deadline)}</span>}
        <span
          className={
            "status " + (row?.status === "submitted" ? "confirmed" : "draft")
          }
        >
          {(
            {
              draft: "下書き",
              submitted: "提出済み",
              returned: "差し戻し",
            } as Record<string, string>
          )[row?.status || ""] || "未提出"}
        </span>
      </div>
      <ErrorBox message={error} />
      {!window ? (
        <Empty>この月の勤務希望はまだ募集されていません。</Empty>
      ) : (
        <>
          <p className="hint">
            勤務できる日・できない日を入力して保存し、内容を確認して提出してください。未入力の日は勤務可能として扱いません。
          </p>
          {row?.reason && (
            <div className="notice-box">差し戻し理由：{row.reason}</div>
          )}
          {closed && (
            <p className="notice-box">
              提出期限を過ぎています。提出済みの希望は差し戻し後に修正できます。未提出の場合は、管理者が募集期間を延長してください。
            </p>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void save();
            }}
          >
            <div className="panel request-list">
              {dates.map((d) => (
                <div className="request-day" key={d}>
                  <strong>{shortDate(d)}</strong>
                  <select
                    aria-label={`${d}の希望`}
                    disabled={row?.status === "submitted" || busy || closed}
                    value={days[d]?.kind || ""}
                    onChange={(e) => set(d, "kind", e.target.value)}
                  >
                    <option value="">未入力</option>
                    <option value="available">勤務可能</option>
                    <option value="unavailable">勤務不可</option>
                    <option value="prefer_off">希望休</option>
                  </select>
                  {days[d]?.kind === "available" ? (
                    <div className="row">
                      <input
                        aria-label={`${d}の開始`}
                        type="time"
                        value={(days[d]?.start || "09:00").slice(0, 5)}
                        disabled={row?.status === "submitted" || busy || closed}
                        onChange={(e) => set(d, "start", e.target.value)}
                      />
                      <span>〜</span>
                      <input
                        aria-label={`${d}の終了`}
                        type="time"
                        value={(days[d]?.end || "18:00").slice(0, 5)}
                        disabled={row?.status === "submitted" || busy || closed}
                        onChange={(e) => set(d, "end", e.target.value)}
                      />
                    </div>
                  ) : (
                    <span />
                  )}
                  <input
                    aria-label={`${d}の備考`}
                    placeholder="備考（任意）"
                    disabled={
                      row?.status === "submitted" ||
                      busy ||
                      closed ||
                      !days[d]?.kind
                    }
                    value={days[d]?.note || ""}
                    onChange={(e) => set(d, "note", e.target.value)}
                  />
                </div>
              ))}
            </div>
            <div className="sticky-actions">
              {row?.status === "submitted" ? (
                onReturn ? (
                  <div className="return-request">
                    <label>
                      差し戻し理由
                      <input
                        aria-label="差し戻し理由"
                        required
                        maxLength={300}
                        value={reason}
                        disabled={busy}
                        onChange={(e) => setReason(e.target.value)}
                      />
                    </label>
                    <button
                      type="button"
                      className="button secondary"
                      disabled={busy || !reason.trim()}
                      onClick={() => void save("return")}
                    >
                      差し戻して編集
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    className="button secondary"
                    disabled={busy || closed}
                    onClick={() => void save("withdraw")}
                  >
                    提出を取り下げる
                  </button>
                )
              ) : (
                <>
                  <Submit busy={busy} disabled={closed} text="下書きを保存" />
                  <button
                    type="button"
                    className="button primary"
                    disabled={busy || closed || dirty || !row?.days.length}
                    onClick={() => void save("submit")}
                  >
                    {proxy ? "勤務希望を代理提出" : "勤務希望を提出"}
                  </button>
                  {dirty && <small>保存してから提出できます。</small>}
                </>
              )}
            </div>
          </form>
        </>
      )}
    </>
  );
}
