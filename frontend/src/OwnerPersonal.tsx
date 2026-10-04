import { useState } from "react";
import { CalendarDays, Plus } from "lucide-react";
import {
  api,
  today,
  shortDate,
  clock,
  min,
  statuses,
  type Actor,
  type Row,
  type Workspace,
} from "./api";
import { Empty, ErrorBox, Field, Submit } from "./components";
import { EditForm } from "./Forms";
import { MemberRequests } from "./MemberView";

export default function OwnerPersonal({
  actor,
  data,
  scope,
  reload,
  onVisit,
}: {
  actor: Actor;
  data: Workspace;
  scope: string;
  reload: () => Promise<void>;
  onVisit: (staff: Row, month: string, visit?: Row) => void;
}) {
  const profile = data.staff.find((p) => p.user_id === actor.id);
  const candidates = data.staff.filter((p) => p.active && !p.user_id);
  const [selected, setSelected] = useState("");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("requests");
  const [month, setMonth] = useState(today().slice(0, 7));
  const root = `/scopes/${scope}`;
  async function link(e: React.FormEvent) {
    e.preventDefault();
    const person = candidates.find((p) => p.id === selected);
    if (!person) return;
    setBusy(true);
    setError("");
    try {
      await api(`${root}/owner-profile/link`, "POST", {
        staff_id: person.id,
        expected_version: person.version,
      });
      await reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const visits = profile
    ? data.visits
        .filter(
          (v) => v.staff_ids.includes(profile.id) && v.date.startsWith(month),
        )
        .sort((a, b) => (a.date + a.start).localeCompare(b.date + b.start))
    : [];
  return (
    <>
      <ErrorBox message={error} />
      {!profile ? (
        <section className="panel person-card owner-profile">
          <span className="eyebrow">MY SCHEDULE</span>
          <h2>自分のスタッフ情報を設定</h2>
          <p>
            オーナーのアカウントで、自分の勤務希望を入力し、訪問の担当者になることができます。
          </p>
          {candidates.length > 0 && (
            <form onSubmit={link}>
              <Field label="登録済みの自分のスタッフ情報">
                <select
                  aria-label="登録済みの自分のスタッフ情報"
                  required
                  value={selected}
                  onChange={(e) => setSelected(e.target.value)}
                  disabled={busy}
                >
                  <option value="">自分の名前を選んでください</option>
                  {candidates.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}（
                      {p.branch_ids
                        .map(
                          (id: string) =>
                            data.branches.find((b) => b.id === id)?.name,
                        )
                        .join("・")}
                      ）
                    </option>
                  ))}
                </select>
              </Field>
              <Submit busy={busy} text="選択したスタッフを自分に設定" />
            </form>
          )}
          <p className="hint">
            既存のスタッフを選ぶと、その人の訪問予定や勤務希望を引き継ぎます。自分の情報がまだない場合は、新しく登録してください。
          </p>
          <button
            className="button secondary"
            disabled={busy}
            onClick={() => setEditing(true)}
          >
            <Plus size={16} />
            自分のスタッフ情報を新規登録
          </button>
        </section>
      ) : (
        <>
          <section className="panel person-card owner-profile">
            <div className="row between">
              <div>
                <span className="eyebrow">MY SCHEDULE</span>
                <h2>{profile.name}</h2>
                <p>
                  {profile.job} ·{" "}
                  {profile.branch_ids
                    .map(
                      (id: string) =>
                        data.branches.find((b) => b.id === id)?.name,
                    )
                    .join("・")}
                </p>
              </div>
              <button
                className="button secondary"
                onClick={() => setEditing(true)}
              >
                自分のスタッフ情報を編集
              </button>
            </div>
            <p className="hint">
              自分の勤務希望と担当する訪問を管理できます。訪問予定表でも、自分を担当者に選べます。
            </p>
          </section>
          {!profile.active ? (
            <Empty>
              スタッフ情報が無効です。「自分のスタッフ情報を編集」で有効にしてください。
            </Empty>
          ) : (
            <>
              <div className="toolbar" aria-label="自分の予定の表示切替">
                <button
                  className={`button ${tab === "requests" ? "primary" : "secondary"}`}
                  onClick={() => setTab("requests")}
                >
                  自分の勤務希望
                </button>
                <button
                  className={`button ${tab === "visits" ? "primary" : "secondary"}`}
                  onClick={() => setTab("visits")}
                >
                  自分の訪問予定
                </button>
              </div>
              <div hidden={tab !== "requests"}>
                <MemberRequests
                  key={profile.id}
                  targetName={profile.name}
                  data={{
                    windows: data.windows,
                    submissions: data.submissions.filter(
                      (s) => s.staff_id === profile.id,
                    ),
                  }}
                  reload={reload}
                  onReturn={async (row, reason) => {
                    await api(
                      `${root}/request-submissions/${row.id}/return`,
                      "POST",
                      { expected_version: row.version, reason },
                    );
                  }}
                />
              </div>
              {tab === "visits" && (
                <>
                  <div className="toolbar">
                    <CalendarDays size={19} />
                    <input
                      aria-label="自分の訪問の対象月"
                      type="month"
                      value={month}
                      onChange={(e) =>
                        e.target.value && setMonth(e.target.value)
                      }
                    />
                    <button
                      className="button primary"
                      onClick={() => onVisit(profile, month)}
                    >
                      <Plus size={16} />
                      自分の訪問予定を追加
                    </button>
                  </div>
                  {visits.length === 0 ? (
                    <Empty>この月の自分の訪問予定はありません。</Empty>
                  ) : (
                    <div className="member-visits">
                      {visits.map((v) => (
                        <article className="panel person-card" key={v.id}>
                          <div className="row between">
                            <strong>
                              {shortDate(v.date)} {v.start}–
                              {clock(min(v.start) + v.duration)}
                            </strong>
                            <span className={`status ${v.status}`}>
                              {statuses[v.status]}
                            </span>
                          </div>
                          <h2>
                            {
                              data.clients.find((c) => c.id === v.client_id)
                                ?.label
                            }
                          </h2>
                          <p>
                            {
                              data.services.find((s) => s.id === v.service_id)
                                ?.name
                            }{" "}
                            ·{" "}
                            {
                              data.branches.find((b) => b.id === v.branch_id)
                                ?.name
                            }
                          </p>
                          <button
                            className="button secondary"
                            onClick={() => onVisit(profile, month, v)}
                          >
                            予定を確認・編集
                          </button>
                        </article>
                      ))}
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </>
      )}
      {editing && (
        <EditForm
          kind="staff"
          title={
            profile ? "自分のスタッフ情報を編集" : "自分のスタッフ情報を登録"
          }
          row={profile}
          defaults={{ name: actor.name }}
          savePath={profile ? undefined : `${root}/owner-profile`}
          data={data}
          scope={scope}
          onClose={() => setEditing(false)}
          onSaved={reload}
        />
      )}
    </>
  );
}
