import { useCallback, useEffect, useState } from "react";
import {
  House,
  CalendarDays,
  ClipboardCheck,
  Users,
  MapPin,
  Building2,
  Route,
  ChartNoAxesCombined,
  Settings,
  ChevronDown,
  Plus,
  Search,
  Leaf,
  Check,
  Bell,
  LogOut,
  Menu,
  ShieldCheck,
  ArrowUpRight,
} from "lucide-react";
import {
  api,
  today,
  statuses,
  type Actor,
  type Row,
  type Workspace,
} from "./api";
import { Brand, ErrorBox, Field, Empty, Submit, Modal } from "./components";
import { EditForm, SmallForm } from "./Forms";
import Schedule from "./Schedule";
import MapView from "./MapView";
import { MemberSchedule, MemberRequests } from "./MemberView";
import OwnerPersonal from "./OwnerPersonal";

const ownerMenus = [
  ["schedule", "訪問予定", CalendarDays],
  ["review", "未調整・確認", ClipboardCheck],
  ["requests", "勤務希望", ClipboardCheck],
  ["personal", "自分の予定・希望", CalendarDays],
  ["clients", "利用者・訪問先", House],
  ["map", "訪問先の地図", MapPin],
  ["staff", "スタッフ・メンバー", Users],
  ["branches", "営業所", Building2],
  ["services", "業務", Route],
  ["reports", "集計・配布", ChartNoAxesCombined],
  ["settings", "設定・変更履歴", Settings],
] as const;
const memberMenus = [
  ["today", "今日の予定", House],
  ["schedule", "自分のシフト", CalendarDays],
  ["requests", "勤務希望", ClipboardCheck],
  ["map", "訪問先の地図", MapPin],
  ["notices", "お知らせ", Bell],
  ["settings", "アカウント", Settings],
] as const;
const descriptions: Record<string, string> = {
  schedule: "みんなの訪問と移動を、ひとつの予定表に。",
  review: "予定の重なりや不足を確認して、安心して訪問できる一日に。",
  clients: "その方らしい暮らしへ。訪問先の情報をひとつに。",
  map: "訪問する場所と、初めてでも迷わないための案内。",
  staff: "それぞれの得意と、働き方を大切に。",
  branches: "複数の営業所を、ひとつのワークスペースで。",
  services: "現場に合わせて、担当できる業務を整えましょう。",
  requests: "みんなの勤務希望を、予定づくりにつなげましょう。",
  personal: "オーナーとして働く、自分の一日も大切に。",
  reports: "訪問と勤務を振り返り、次の予定へ。",
  settings: "ワークスペースの設定と、これまでの変更。",
  today: "今日も、ひとつひとつの訪問を大切に。",
  notices: "あなたの予定に関するお知らせです。",
  admin: "会社とオーナーを登録し、それぞれの訪問を支えます。",
};

function Login({ onLogin }: { onLogin: (a: Actor) => void }) {
  const token = new URLSearchParams(location.hash.slice(1)).get("setup");
  const [login, setLogin] = useState(""),
    [password, setPassword] = useState(""),
    [confirm, setConfirm] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [done, setDone] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (token && !done) {
        if (password !== confirm)
          throw new Error("確認用パスワードが一致しません");
        await api("/auth/setup", "POST", { token, password });
        history.replaceState(null, "", location.pathname);
        setDone(true);
        setPassword("");
      } else
        onLogin(
          await api("/auth/login", "POST", { login_id: login, password }),
        );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-shell">
      <div className="login-art">
        <span className="eyebrow">A LITTLE CARE, EVERY DAY</span>
        <h1>
          暮らしをつなぐ、
          <br />
          やさしい予定。
        </h1>
        <p>
          訪問する人も、待っている人も。
          <br />
          それぞれの一日を、ていねいに。
        </p>
        <div className="house-illustration">
          <House size={135} strokeWidth={0.7} />
          <Leaf size={48} strokeWidth={1} />
        </div>
      </div>
      <section className="panel login-card">
        <Brand />
        <h2>{token && !done ? "パスワードを設定" : "おかえりなさい"}</h2>
        <p>
          {done
            ? "設定が完了しました。ログインしてください。"
            : token
              ? "12文字以上のパスワードを設定してください。"
              : "あなたのワークスペースをひらきましょう。"}
        </p>
        <ErrorBox message={error} />
        <form onSubmit={submit}>
          {(!token || done) && (
            <Field label="ログインID">
              <input
                autoComplete="username"
                required
                value={login}
                onChange={(e) => setLogin(e.target.value)}
              />
            </Field>
          )}
          <Field label="パスワード">
            <input
              type="password"
              autoComplete={
                token && !done ? "new-password" : "current-password"
              }
              minLength={token && !done ? 12 : 1}
              maxLength={200}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          {token && !done && (
            <Field label="パスワード（確認）">
              <input
                type="password"
                autoComplete="new-password"
                minLength={12}
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            </Field>
          )}
          <Submit
            busy={busy}
            text={token && !done ? "パスワードを設定" : "ログイン"}
          />
        </form>
        <small>訪問のアトリエ · Web版</small>
      </section>
    </div>
  );
}

export default function App() {
  const [actor, setActor] = useState<Actor | null>(null),
    [checked, setChecked] = useState(false),
    [scope, setScope] = useState(""),
    [data, setData] = useState<Workspace | null>(null),
    [member, setMember] = useState<any>(null),
    [admin, setAdmin] = useState<any>(null),
    [page, setPage] = useState("schedule"),
    [branch, setBranch] = useState(""),
    [search, setSearch] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [mobile, setMobile] = useState(false);
  const [edit, setEdit] = useState<{
      kind: string;
      row?: Row;
      defaults?: Record<string, unknown>;
    } | null>(null),
    [small, setSmall] = useState<any>(null);
  const [requestEditor, setRequestEditor] = useState<{
    staffId: string;
    month: string;
  } | null>(null);
  const [requestEditState, setRequestEditState] = useState({
    dirty: false,
    busy: false,
  });
  function signedIn(a: Actor) {
    setActor(a);
    setScope(a.scope_id || "");
    setPage(
      a.role === "system_admin"
        ? "admin"
        : a.role === "member"
          ? "today"
          : "schedule",
    );
    setBranch("");
    setData(null);
    setMember(null);
    setError("");
  }
  useEffect(() => {
    void api<Actor>("/auth/me")
      .then(signedIn)
      .catch(() => {})
      .finally(() => setChecked(true));
  }, []);
  const reload = useCallback(async () => {
    if (!actor) return;
    if (actor.role === "member") setMember(await api("/me/schedule"));
    else {
      if (actor.role === "system_admin") setAdmin(await api("/admin/overview"));
      if (scope) setData(await api(`/scopes/${scope}/workspace`));
    }
  }, [actor, scope]);
  useEffect(() => {
    setBusy(true);
    void reload()
      .catch((e) => setError(e.message))
      .finally(() => setBusy(false));
  }, [reload]);
  async function action(path: string, method = "POST", body?: unknown) {
    setError("");
    try {
      const value = await api(path, method, body);
      await reload();
      return value;
    } catch (e) {
      setError((e as Error).message);
      throw e;
    }
  }
  async function logout() {
    try {
      await api("/auth/logout", "POST");
      setActor(null);
      setData(null);
      setMember(null);
      setAdmin(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  function navigate(p: string) {
    setPage(p);
    setSearch("");
    setMobile(false);
    setError("");
  }
  const root = `/scopes/${scope}`;
  function position(c: Row) {
    setSmall({
      title: "訪問先の位置を設定",
      initial: { latitude: c.latitude ?? "", longitude: c.longitude ?? "" },
      fields: [
        { key: "latitude", label: "緯度", type: "number" },
        { key: "longitude", label: "経度", type: "number" },
      ],
      onSubmit: async (v: any) =>
        action(`${root}/clients/${c.id}/coordinates`, "PATCH", {
          ...v,
          expected_version: c.version,
        }),
    });
  }
  function password() {
    setSmall({
      title: "パスワードを変更",
      fields: [
        {
          key: "current_password",
          label: "現在のパスワード",
          type: "password",
        },
        {
          key: "password",
          label: "新しいパスワード（12文字以上）",
          type: "password",
        },
      ],
      onSubmit: async (v: any) => {
        await api("/auth/password", "POST", v);
        setActor(null);
        setSmall(null);
      },
    });
  }
  if (!checked)
    return (
      <div className="loading">
        <Leaf size={35} />
        <p>アトリエをひらいています…</p>
      </div>
    );
  if (!actor) return <Login onLogin={signedIn} />;
  const isMember = actor.role === "member",
    menus = isMember
      ? memberMenus
      : ownerMenus.filter((x) => x[0] !== "personal" || actor.role === "owner"),
    title =
      page === "admin"
        ? "会社とオーナー"
        : menus.find((x) => x[0] === page)?.[1] || "訪問予定";
  const filtered = (list: Row[]) =>
    list.filter(
      (x) =>
        (!branch || !x.branch_ids || x.branch_ids.includes(branch)) &&
        (!search ||
          `${x.name} ${x.address || ""} ${x.job || ""}`.includes(search)),
    );
  function csv() {
    if (!data) return;
    const rows = [
      ["日付", "開始", "利用者", "業務", "営業所", "担当者", "状態"],
      ...data.visits
        .filter(
          (v) =>
            (!branch || v.branch_id === branch) &&
            v.date.startsWith(today().slice(0, 7)),
        )
        .map((v) => [
          v.date,
          v.start,
          data.clients.find((c) => c.id === v.client_id)?.label,
          data.services.find((s) => s.id === v.service_id)?.name,
          data.branches.find((b) => b.id === v.branch_id)?.name,
          v.staff_ids
            .map((id: string) => data.staff.find((p) => p.id === id)?.name)
            .join("・"),
          statuses[v.status],
        ]),
    ];
    const text =
      "\uFEFF" +
      rows
        .map((row) =>
          row
            .map((value) => {
              let s = String(value ?? "");
              if (/^[=+@\-\t\r]/.test(s)) s = "'" + s;
              return '"' + s.replaceAll('"', '""') + '"';
            })
            .join(","),
        )
        .join("\r\n");
    const url = URL.createObjectURL(
      new Blob([text], { type: "text/csv;charset=utf-8" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `訪問予定_${today().slice(0, 7)}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <div className="app-shell">
      <aside className={"sidebar " + (mobile ? "open" : "")}>
        <div className="sidebar-brand">
          <Brand />
          <p className="brand-tagline">暮らしをつなぐ、やさしい予定。</p>
        </div>
        <div className="workspace-card">
          <House size={22} />
          <div>
            <strong>{data?.company.name || "訪問ケアのワークスペース"}</strong>
            <small>
              {isMember
                ? "あなたの担当予定"
                : actor.role === "system_admin"
                  ? "システム管理者"
                  : "複数の営業所をつなぐ"}
            </small>
          </div>
        </div>
        <nav>
          {actor.role === "system_admin" && (
            <button
              className={"nav-item " + (page === "admin" ? "active" : "")}
              onClick={() => navigate("admin")}
            >
              <ShieldCheck size={19} />
              会社とオーナー
            </button>
          )}
          {menus.map(([id, label, Icon], i) => (
            <div key={id}>
              {(i === 0 ||
                (isMember
                  ? i === 3
                  : id === "clients" || id === "reports")) && (
                <div className="nav-caption">
                  {i === 0
                    ? "SCHEDULE"
                    : id === "clients" || isMember
                      ? "PEOPLE & PLANS"
                      : "WORKSPACE"}
                </div>
              )}
              <button
                disabled={!isMember && !scope}
                className={"nav-item " + (page === id ? "active" : "")}
                onClick={() => navigate(id)}
              >
                <Icon size={19} />
                {label}
                {id === "review" &&
                  data &&
                  data.issues.filter((i) => i.level === "error").length > 0 && (
                    <b>
                      {data.issues.filter((i) => i.level === "error").length}
                    </b>
                  )}
              </button>
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div>
            <strong>{actor.name}</strong>
            <small>
              {
                {
                  system_admin: "システム管理者",
                  owner: "オーナー",
                  member: "メンバー",
                }[actor.role]
              }
            </small>
          </div>
          <button
            className="icon-button"
            aria-label="ログアウト"
            onClick={() => void logout()}
          >
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      {mobile && (
        <button
          className="mobile-backdrop"
          aria-label="メニューを閉じる"
          onClick={() => setMobile(false)}
        />
      )}
      <div className="main-shell">
        <header className="topbar">
          <div className="row">
            <button
              className="icon-button mobile-menu"
              aria-label="メニュー"
              onClick={() => setMobile(!mobile)}
            >
              <Menu />
            </button>
            <Leaf size={17} />
            <span className="breadcrumb">ワークスペース　›　{title}</span>
          </div>
          <div className="row">
            {!isMember && data && (
              <select
                className="branch-select"
                aria-label="営業所の表示切替"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
              >
                <option value="">すべての営業所</option>
                {data.branches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            )}
            <small className="save-state">
              <Check size={14} />
              {busy ? "読み込み中" : "接続済み"}
            </small>
          </div>
        </header>
        <main>
          <div className="page-title">
            <div>
              <span className="eyebrow">A LITTLE CARE, EVERY DAY</span>
              <h1>{title}</h1>
              <p>{descriptions[page]}</p>
            </div>
            <span className="date-heading">
              {new Date().toLocaleDateString("ja-JP", {
                year: "numeric",
                month: "long",
              })}
            </span>
          </div>
          <ErrorBox message={error} />
          {error && (
            <button
              className="button secondary"
              onClick={() =>
                void reload()
                  .then(() => setError(""))
                  .catch((e) => setError(e.message))
              }
            >
              再読み込み
            </button>
          )}
          {page === "admin" && admin && (
            <>
              <div className="toolbar">
                <button
                  className="button primary"
                  onClick={() =>
                    setSmall({
                      title: "会社を登録",
                      fields: [
                        { key: "name", label: "会社名" },
                        { key: "contact", label: "連絡先" },
                      ],
                      onSubmit: (v: any) =>
                        action("/admin/companies", "POST", v),
                    })
                  }
                >
                  <Plus size={16} />
                  会社を登録
                </button>
                <button
                  className="button secondary"
                  onClick={() =>
                    setSmall({
                      title: "オーナーを登録",
                      fields: [
                        {
                          key: "company_id",
                          label: "会社",
                          options: admin.companies.map((c: Row) => ({
                            id: c.id,
                            name: c.name,
                          })),
                        },
                        { key: "name", label: "オーナー名" },
                        { key: "login_id", label: "ログインID" },
                      ],
                      onSubmit: (v: any) => action("/admin/owners", "POST", v),
                    })
                  }
                >
                  オーナーを登録
                </button>
              </div>
              <div className="card-grid">
                {admin.companies.map((c: Row) => (
                  <article className="panel person-card" key={c.id}>
                    <Building2 className="avatar-icon" />
                    <h2>{c.name}</h2>
                    <p>{c.contact}</p>
                    {admin.scopes
                      .filter((s: Row) => s.company_id === c.id)
                      .map((s: Row) => (
                        <button
                          key={s.id}
                          className="scope-button"
                          onClick={() => {
                            setScope(s.id);
                            setData(null);
                            setBranch("");
                            navigate("schedule");
                          }}
                        >
                          {s.name}
                          <ArrowUpRight size={16} />
                        </button>
                      ))}
                  </article>
                ))}
              </div>
            </>
          )}
          {!isMember && scope && !data && !error && (
            <Empty>ワークスペースを読み込んでいます…</Empty>
          )}
          {!isMember && data && page === "schedule" && (
            <Schedule
              data={data}
              scope={scope}
              branch={branch}
              onEdit={(v) => setEdit({ kind: "visits", row: v })}
              onNew={(defaults) => setEdit({ kind: "visits", defaults })}
              reload={reload}
            />
          )}
          {!isMember && data && page === "review" && (
            <div className="panel issue-list">
              {data.issues.length ? (
                data.issues.map((issue, i) => (
                  <div key={i} className="issue">
                    <span
                      className={
                        "status " +
                        (issue.level === "error" ? "draft" : "confirmed")
                      }
                    >
                      {issue.level === "error" ? "要調整" : "確認"}
                    </span>
                    <p>{issue.message}</p>
                    <button
                      className="button subtle"
                      onClick={() =>
                        setEdit({
                          kind: "visits",
                          row: data.visits.find(
                            (v) => v.id === issue.visit_ids[0],
                          ),
                        })
                      }
                    >
                      予定を確認
                    </button>
                  </div>
                ))
              ) : (
                <Empty>確認が必要な予定はありません。</Empty>
              )}
            </div>
          )}
          {!isMember &&
            data &&
            ["staff", "clients", "branches", "services"].includes(page) && (
              <>
                <div className="toolbar">
                  <div className="search">
                    <Search size={18} />
                    <input
                      aria-label="一覧を検索"
                      placeholder="名前や住所で検索"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                  </div>
                  <button
                    className="button primary push"
                    onClick={() => setEdit({ kind: page })}
                  >
                    <Plus size={17} />
                    {
                      (
                        {
                          staff: "スタッフ",
                          clients: "利用者",
                          branches: "営業所",
                          services: "業務",
                        } as Record<string, string>
                      )[page]
                    }
                    を追加
                  </button>
                </div>
                <div className="card-grid">
                  {filtered(
                    data[page as "staff" | "clients" | "branches" | "services"],
                  ).map((row, i) => (
                    <article className="panel person-card" key={row.id}>
                      <div className="row between">
                        <div className={"avatar tone-" + (i % 4)}>
                          {page === "staff" ? (
                            <Users />
                          ) : page === "clients" ? (
                            <House />
                          ) : page === "branches" ? (
                            <Building2 />
                          ) : (
                            <Route />
                          )}
                        </div>
                        <button
                          className="button subtle"
                          onClick={() => setEdit({ kind: page, row })}
                        >
                          編集
                        </button>
                      </div>
                      <h2>{row.label || row.name}</h2>
                      <p>
                        {row.job ||
                          row.address ||
                          (row.duration
                            ? `${row.duration}分 · ${row.people}人で訪問`
                            : "詳細を登録しましょう")}
                      </p>
                      {row.active === false && (
                        <span className="status cancelled">無効</span>
                      )}
                      <div className="tags">
                        {row.branch_ids?.map((id: string) => (
                          <span key={id}>
                            {data.branches.find((b) => b.id === id)?.name}
                          </span>
                        ))}
                        {row.service_ids?.map((id: string) => (
                          <span key={id}>
                            {data.services.find((s) => s.id === id)?.name}
                          </span>
                        ))}
                      </div>
                      {page === "staff" && (
                        <>
                          <p>
                            {row.start}–{row.end} · 上限
                            {row.max_visits || "なし"}件/日
                          </p>
                          <div className="card-actions">
                            {row.account_role === "owner" ? (
                              <span className="status confirmed">
                                オーナー本人
                              </span>
                            ) : (
                              <button
                                className="button secondary"
                                onClick={() =>
                                  row.user_id
                                    ? setSmall({
                                        title: "初回・再設定リンクを発行",
                                        fields: [],
                                        onSubmit: () =>
                                          action(
                                            `${root}/staff/${row.id}/setup-token`,
                                          ),
                                      })
                                    : setSmall({
                                        title: "メンバーアカウントを登録",
                                        fields: [
                                          {
                                            key: "login_id",
                                            label: "ログインID",
                                          },
                                        ],
                                        onSubmit: (v: any) =>
                                          action(`${root}/members`, "POST", {
                                            ...v,
                                            staff_id: row.id,
                                          }),
                                      })
                                }
                              >
                                {row.user_id
                                  ? "設定リンクを発行"
                                  : "ログインを有効にする"}
                              </button>
                            )}
                            {row.user_id && row.account_role !== "owner" && (
                              <button
                                className="button subtle"
                                onClick={() =>
                                  void action(
                                    `${root}/staff/${row.id}/account`,
                                    "PATCH",
                                    { active: !row.account_active },
                                  ).catch(() => {})
                                }
                              >
                                {row.account_active
                                  ? "アカウントを停止"
                                  : "利用を再開"}
                              </button>
                            )}
                            <button
                              className="button subtle"
                              onClick={() =>
                                setSmall({
                                  title: "雇用・費用条件を追加",
                                  initial: {
                                    effective_from: today(),
                                    employment: "パート・アルバイト",
                                    basis: "hourly",
                                    amount: 0,
                                  },
                                  fields: [
                                    {
                                      key: "effective_from",
                                      label: "適用開始日",
                                      type: "date",
                                    },
                                    { key: "employment", label: "雇用区分" },
                                    {
                                      key: "basis",
                                      label: "計算方式",
                                      options: [
                                        { id: "unset", name: "未設定" },
                                        { id: "hourly", name: "時給" },
                                        { id: "monthly", name: "月額固定" },
                                      ],
                                    },
                                    {
                                      key: "amount",
                                      label: "金額（円）",
                                      type: "number",
                                    },
                                  ],
                                  onSubmit: (v: any) =>
                                    action(
                                      `${root}/staff/${row.id}/pay-terms`,
                                      "POST",
                                      v,
                                    ),
                                })
                              }
                            >
                              雇用・費用条件を追加
                            </button>
                          </div>
                          <details>
                            <summary>雇用・費用の履歴</summary>
                            {data.pay_terms
                              .filter((t) => t.staff_id === row.id)
                              .sort((a, b) =>
                                b.effective_from.localeCompare(
                                  a.effective_from,
                                ),
                              )
                              .map((t) => (
                                <p key={t.id}>
                                  {t.effective_from}〜 {t.employment} ·{" "}
                                  {t.basis === "hourly"
                                    ? "時給"
                                    : t.basis === "monthly"
                                      ? "月額"
                                      : "未設定"}{" "}
                                  {t.amount.toLocaleString()}円
                                </p>
                              ))}
                          </details>
                        </>
                      )}
                      {page === "clients" && (
                        <>
                          <p>{row.guide || "訪問案内は未登録です。"}</p>
                          <div className="card-actions">
                            <button
                              className="button secondary"
                              onClick={() => position(row)}
                            >
                              {row.geocode_status === "resolved"
                                ? "位置を確認・修正"
                                : "位置を設定"}
                            </button>
                            {data.geocoding_enabled && (
                              <button
                                className="button subtle"
                                onClick={() =>
                                  void action(
                                    `${root}/clients/${row.id}/geocode`,
                                    "POST",
                                    { expected_version: row.version },
                                  ).catch(() => {})
                                }
                              >
                                住所から位置を取得
                              </button>
                            )}
                          </div>
                        </>
                      )}
                    </article>
                  ))}
                </div>
                {filtered(
                  data[page as "staff" | "clients" | "branches" | "services"],
                ).length === 0 && (
                  <Empty>
                    まだ登録がありません。追加ボタンから登録できます。
                  </Empty>
                )}
              </>
            )}
          {!isMember && data && page === "map" && (
            <MapView
              clients={filtered(data.clients)}
              onCoordinates={position}
            />
          )}
          {!isMember && data && page === "requests" && (
            <>
              <div className="toolbar">
                <button
                  className="button primary"
                  onClick={() =>
                    setSmall({
                      title: "勤務希望の募集",
                      initial: {
                        month: today().slice(0, 7),
                        deadline: today(),
                      },
                      fields: [
                        { key: "month", label: "対象月", type: "month" },
                        { key: "deadline", label: "提出期限", type: "date" },
                      ],
                      onSubmit: (v: any) =>
                        action(`${root}/request-windows`, "POST", v),
                    })
                  }
                >
                  <Plus size={16} />
                  募集期間を設定
                </button>
              </div>
              {data.windows.map((w) => (
                <section
                  key={w.id}
                  className="panel person-card request-window"
                >
                  <h2>{w.month}の勤務希望</h2>
                  <p>提出期限：{w.deadline}</p>
                  {data.staff
                    .filter((p) => p.active)
                    .map((p) => {
                      const sub = data.submissions.find(
                        (s) => s.staff_id === p.id && s.month === w.month,
                      );
                      return (
                        <div className="submission" key={p.id}>
                          <div className="row between">
                            <strong>{p.name}</strong>
                            <span
                              className={
                                "status " +
                                (sub?.status === "submitted"
                                  ? "confirmed"
                                  : "draft")
                              }
                            >
                              {sub
                                ? (
                                    {
                                      draft: "下書き",
                                      submitted: "提出済み",
                                      returned: "差し戻し",
                                    } as any
                                  )[sub.status]
                                : "未提出"}
                            </span>
                            <button
                              className="button secondary"
                              onClick={() =>
                                setRequestEditor({
                                  staffId: p.id,
                                  month: w.month,
                                })
                              }
                            >
                              {p.user_id === actor.id
                                ? "自分の希望を入力"
                                : "代理入力"}
                            </button>
                            {sub?.status === "submitted" && (
                              <button
                                className="button subtle"
                                onClick={() =>
                                  setSmall({
                                    title: "勤務希望を差し戻す",
                                    fields: [
                                      { key: "reason", label: "差し戻し理由" },
                                    ],
                                    onSubmit: (v: any) =>
                                      action(
                                        `${root}/request-submissions/${sub.id}/return`,
                                        "POST",
                                        { ...v, expected_version: sub.version },
                                      ),
                                  })
                                }
                              >
                                差し戻す
                              </button>
                            )}
                          </div>
                          {sub && (
                            <details>
                              <summary>
                                希望を確認（{sub.days.length}日分）
                              </summary>
                              {sub.days.map((d: any) => (
                                <p key={d.date}>
                                  {d.date}　
                                  {
                                    (
                                      {
                                        available: "勤務可能",
                                        unavailable: "勤務不可",
                                        prefer_off: "希望休",
                                      } as any
                                    )[d.kind]
                                  }{" "}
                                  {d.kind === "available"
                                    ? `${d.start}〜${d.end}`
                                    : ""}{" "}
                                  {d.note}
                                </p>
                              ))}
                            </details>
                          )}
                        </div>
                      );
                    })}
                </section>
              ))}
              {!data.windows.length && (
                <Empty>勤務希望の募集期間を設定してください。</Empty>
              )}
            </>
          )}
          {actor.role === "owner" && data && page === "personal" && (
            <OwnerPersonal
              actor={actor}
              data={data}
              scope={scope}
              reload={reload}
              onVisit={(staff, month, visit) =>
                setEdit({
                  kind: "visits",
                  row: visit,
                  defaults: {
                    staff_ids: [staff.id],
                    branch_id: staff.branch_ids[0],
                    date: today().startsWith(month) ? today() : `${month}-01`,
                  },
                })
              }
            />
          )}
          {!isMember && data && page === "reports" && (
            <>
              <div className="panel person-card">
                <h2>{today().slice(0, 7)}の訪問予定</h2>
                <p>
                  選択中の営業所に合わせて、今月の訪問予定をCSVに出力します。
                </p>
                <button className="button primary" onClick={csv}>
                  訪問予定をCSVで保存
                </button>
              </div>
              <div className="card-grid report-grid">
                {data.staff
                  .filter((p) => !branch || p.branch_ids.includes(branch))
                  .map((p) => {
                    const vs = data.visits.filter(
                      (v) =>
                        v.date.startsWith(today().slice(0, 7)) &&
                        v.status !== "cancelled" &&
                        v.staff_ids.includes(p.id) &&
                        (!branch || v.branch_id === branch),
                    );
                    return (
                      <article className="panel person-card" key={p.id}>
                        <h2>{p.name}</h2>
                        <p>今月の訪問 {vs.length}件</p>
                        <strong className="report-number">
                          {(
                            vs.reduce((sum, v) => sum + v.duration, 0) / 60
                          ).toFixed(1)}
                          <small>時間</small>
                        </strong>
                        <p className="hint">
                          訪問時間の合計です。勤務時間・給与とは異なります。
                        </p>
                      </article>
                    );
                  })}
              </div>
            </>
          )}
          {isMember &&
            member &&
            ["today", "schedule", "map"].includes(page) && (
              <MemberSchedule data={member} page={page} />
            )}
          {isMember && member && page === "requests" && (
            <MemberRequests data={member} reload={reload} />
          )}
          {isMember && member && page === "notices" && (
            <div className="panel issue-list">
              {[...member.notices].reverse().map((n: Row) => (
                <div className="issue" key={n.id}>
                  <Bell size={18} />
                  <p>{n.text}</p>
                  {!n.read && (
                    <button
                      className="button secondary"
                      onClick={() =>
                        void action(`/me/notices/${n.id}/read`).catch(() => {})
                      }
                    >
                      既読にする
                    </button>
                  )}
                </div>
              ))}
              {!member.notices.length && (
                <Empty>新しいお知らせはありません。</Empty>
              )}
            </div>
          )}
          {page === "settings" && (
            <>
              <section className="panel person-card">
                <h2>アカウント</h2>
                <p>{actor.name}</p>
                <button className="button secondary" onClick={password}>
                  パスワードを変更
                </button>
                <button className="button subtle" onClick={() => void logout()}>
                  ログアウト
                </button>
              </section>
              {!isMember && data && (
                <section className="panel person-card history-panel">
                  <h2>変更履歴</h2>
                  <p>最近の50件を表示しています。</p>
                  {data.history.map((h) => (
                    <div className="history-row" key={h.id}>
                      <small>
                        {new Date(h.created_at).toLocaleString("ja-JP")}
                      </small>
                      <span>{h.summary}</span>
                    </div>
                  ))}
                </section>
              )}
            </>
          )}
        </main>
        <footer>
          <span>訪問のアトリエ</span>
          <small>暮らしをつなぐ、やさしい予定。　Web版 0.1</small>
        </footer>
      </div>
      {isMember && (
        <nav className="bottom-nav">
          {memberMenus.slice(0, 4).map(([id, label, Icon]) => (
            <button
              key={id}
              className={page === id ? "active" : ""}
              onClick={() => navigate(id)}
            >
              <Icon size={20} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      )}
      {edit && data && (
        <EditForm
          key={edit.kind + (edit.row?.id || "new")}
          kind={edit.kind}
          row={edit.row}
          defaults={edit.defaults}
          data={data}
          scope={scope}
          onClose={() => setEdit(null)}
          onSaved={reload}
        />
      )}
      {requestEditor && data && (
        <Modal
          title="勤務希望の入力"
          wide
          onClose={() => {
            if (
              !requestEditState.busy &&
              (!requestEditState.dirty ||
                globalThis.confirm("保存していない変更を破棄して閉じますか？"))
            )
              setRequestEditor(null);
          }}
        >
          <MemberRequests
            key={requestEditor.staffId + requestEditor.month}
            targetName={
              data.staff.find((p) => p.id === requestEditor.staffId)?.name
            }
            proxy={
              data.staff.find((p) => p.id === requestEditor.staffId)
                ?.user_id !== actor.id
            }
            requestBase={`${root}/staff/${requestEditor.staffId}/requests`}
            initialMonth={requestEditor.month}
            onEditState={setRequestEditState}
            data={{
              windows: data.windows,
              submissions: data.submissions.filter(
                (s) => s.staff_id === requestEditor.staffId,
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
        </Modal>
      )}
      {small && <SmallForm {...small} onClose={() => setSmall(null)} />}
    </div>
  );
}
