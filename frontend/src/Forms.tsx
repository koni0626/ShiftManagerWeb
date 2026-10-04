import { useState, type FormEvent } from "react";
import { api, today, type Row, type Workspace, statuses } from "./api";
import { Modal, Field, ErrorBox, Submit } from "./components";

type Props = {
  kind: string;
  row?: Row;
  data: Workspace;
  scope: string;
  onClose: () => void;
  onSaved: () => Promise<void>;
  defaults?: Record<string, unknown>;
  savePath?: string;
  title?: string;
};
const labels: Record<string, string> = {
  branches: "営業所",
  staff: "スタッフ",
  clients: "利用者・訪問先",
  services: "業務",
  visits: "訪問予定",
};
export function EditForm({
  kind,
  row,
  data,
  scope,
  onClose,
  onSaved,
  defaults = {},
  savePath,
  title,
}: Props) {
  const [form, setForm] = useState<Record<string, any>>(() => {
    const base: Record<string, any> = {
      name: "",
      active: true,
      branch_ids: data.branches
        .filter((b) => b.active)
        .slice(0, 1)
        .map((b) => b.id),
      start: "09:00",
      end: "18:00",
      weekdays: [0, 1, 2, 3, 4],
      ...defaults,
    };
    if (kind === "staff")
      Object.assign(base, {
        job: "ヘルパー",
        service_ids: data.services
          .filter((s) => s.jobs.includes("ヘルパー"))
          .map((s) => s.id),
        qualifications: [],
        max_visits: 8,
        break_start: "12:00",
        break_end: "13:00",
      });
    if (kind === "clients")
      Object.assign(base, {
        label: "",
        address: "",
        building: "",
        phone: "",
        guide: "",
        private_note: "",
        weekdays: [0, 1, 2, 3, 4, 5, 6],
      });
    if (kind === "branches") Object.assign(base, { address: "", phone: "" });
    if (kind === "services")
      Object.assign(base, {
        duration: 60,
        people: 1,
        jobs: ["ヘルパー"],
        qualifications: [],
      });
    if (kind === "visits")
      Object.assign(base, {
        branch_id: data.branches.find((b) => b.active)?.id || "",
        client_id: data.clients.find((c) => c.active)?.id || "",
        service_id: data.services.find((s) => s.active)?.id || "",
        date: today(),
        start: "09:00",
        duration: data.services[0]?.duration || 60,
        people: 1,
        staff_ids: [],
        note: "",
        ...defaults,
      });
    return { ...base, ...defaults, ...row };
  });
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [dirty, setDirty] = useState(false);
  const set = (key: string, value: any) => {
    setDirty(true);
    setForm((f) => ({ ...f, [key]: value }));
  };
  const toggle = (key: string, value: any) =>
    set(
      key,
      form[key].includes(value)
        ? form[key].filter((x: any) => x !== value)
        : [...form[key], value],
    );
  const root = `/scopes/${scope}`;
  const input = (
    key: string,
    label: string,
    type = "text",
    required = false,
    wide = false,
  ) => (
    <Field label={label} wide={wide}>
      <input
        type={type}
        required={required}
        value={form[key] ?? ""}
        onChange={(e) =>
          set(key, type === "number" ? Number(e.target.value) : e.target.value)
        }
        min={type === "number" ? 0 : undefined}
      />
    </Field>
  );
  const picks = (
    key: string,
    label: string,
    options: { id: any; name: string }[],
  ) => (
    <fieldset className="span-2">
      <legend>{label}</legend>
      <div className="choices">
        {options.map((x) => (
          <label key={x.id}>
            <input
              type="checkbox"
              checked={(form[key] || []).includes(x.id)}
              onChange={() => toggle(key, x.id)}
            />
            <span>{x.name}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
  const select = (key: string, label: string, options: Row[]) => (
    <Field label={label}>
      <select
        required
        value={form[key]}
        onChange={(e) => {
          set(key, e.target.value);
          if (key === "service_id") {
            const service = data.services.find((s) => s.id === e.target.value)!;
            setForm((f) => ({
              ...f,
              service_id: service.id,
              duration: service.duration,
              people: service.people,
            }));
          }
        }}
      >
        <option value="" disabled>
          選択してください
        </option>
        {options.map((x) => (
          <option key={x.id} value={x.id}>
            {x.label || x.name}
          </option>
        ))}
      </select>
    </Field>
  );
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const keys: Record<string, string[]> = {
      branches: ["name", "address", "phone", "active"],
      staff: [
        "name",
        "job",
        "branch_ids",
        "service_ids",
        "qualifications",
        "weekdays",
        "start",
        "end",
        "break_start",
        "break_end",
        "max_visits",
        "active",
      ],
      clients: [
        "name",
        "label",
        "branch_ids",
        "address",
        "building",
        "phone",
        "guide",
        "private_note",
        "weekdays",
        "start",
        "end",
        "active",
      ],
      services: [
        "name",
        "duration",
        "people",
        "jobs",
        "qualifications",
        "active",
      ],
      visits: [
        "branch_id",
        "client_id",
        "service_id",
        "date",
        "start",
        "duration",
        "people",
        "staff_ids",
        "note",
      ],
    };
    const body = Object.fromEntries(
      keys[kind].map((k) => [
        k,
        k === "break_start" || k === "break_end" ? form[k] || null : form[k],
      ]),
    );
    if (row) body.expected_version = row.version;
    try {
      await api(
        savePath || `${root}/${kind}${row ? "/" + row.id : ""}`,
        row ? "PATCH" : "POST",
        body,
      );
      await onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function transition(action: string) {
    setBusy(true);
    setError("");
    try {
      await api(`${root}/visits/${row!.id}/${action}`, "POST", {
        expected_version: row!.version,
      });
      await onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const editable = kind !== "visits" || !row || row.status === "draft";
  return (
    <Modal
      title={title || `${labels[kind]}${row ? "を確認・編集" : "を追加"}`}
      onClose={onClose}
      wide
    >
      <ErrorBox message={error} />
      <form onSubmit={save}>
        <fieldset disabled={busy || !editable} className="form-grid plain">
          {kind !== "visits" &&
            input("name", kind === "clients" ? "氏名" : "名前", "text", true)}
          {kind === "branches" && (
            <>
              {input("phone", "電話番号")}
              {input("address", "住所", "text", false, true)}
            </>
          )}
          {kind === "staff" && (
            <>
              <Field label="職種">
                <select
                  value={form.job}
                  onChange={(e) => set("job", e.target.value)}
                >
                  {["ケアマネジャー", "ヘルパー", "兼務", "未設定"].map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
              </Field>
              {picks(
                "branch_ids",
                "所属営業所",
                data.branches.filter((b) => b.active),
              )}
              {picks(
                "service_ids",
                "担当できる業務",
                data.services.filter((s) => s.active),
              )}
              {input("max_visits", "1日の訪問上限（0＝なし）", "number")}
            </>
          )}
          {kind === "clients" && (
            <>
              {input("label", "シフト表の表示名", "text", true)}
              {picks(
                "branch_ids",
                "訪問できる営業所",
                data.branches.filter((b) => b.active),
              )}
              {input(
                "address",
                "住所（建物・部屋番号を除く）",
                "text",
                false,
                true,
              )}
              {input("building", "建物名・部屋番号")}
              {input("phone", "電話番号")}
              <Field label="メンバー向け訪問案内" wide>
                <textarea
                  value={form.guide}
                  onChange={(e) => set("guide", e.target.value)}
                  placeholder="入口、駐車場所、訪問時に気をつけること"
                />
              </Field>
              <Field label="管理者用メモ（メンバーには非公開）" wide>
                <textarea
                  value={form.private_note}
                  onChange={(e) => set("private_note", e.target.value)}
                />
              </Field>
            </>
          )}
          {["staff", "clients"].includes(kind) && (
            <>
              {picks(
                "weekdays",
                "対応できる曜日",
                "月火水木金土日".split("").map((name, id) => ({ id, name })),
              )}
              {input("start", "開始時刻", "time", true)}
              {input("end", "終了時刻", "time", true)}
            </>
          )}
          {kind === "staff" && (
            <>
              {input("break_start", "休憩開始", "time")}
              {input("break_end", "休憩終了", "time")}
            </>
          )}
          {kind === "services" && (
            <>
              {input("duration", "標準の所要時間（分）", "number", true)}
              {input("people", "必要人数", "number", true)}
              {picks(
                "jobs",
                "対応できる職種",
                ["ケアマネジャー", "ヘルパー", "兼務"].map((x) => ({
                  id: x,
                  name: x,
                })),
              )}
            </>
          )}
          {["staff", "services"].includes(kind) && (
            <Field label="資格タグ（読点で区切る）" wide>
              <input
                value={form.qualifications.join("、")}
                onChange={(e) =>
                  set(
                    "qualifications",
                    e.target.value
                      .split(/[、,]/)
                      .map((x) => x.trim())
                      .filter(Boolean),
                  )
                }
              />
            </Field>
          )}
          {kind === "visits" && (
            <>
              {select(
                "branch_id",
                "営業所",
                data.branches.filter((b) => b.active),
              )}
              {select(
                "client_id",
                "利用者",
                data.clients.filter((c) => c.active),
              )}
              {select(
                "service_id",
                "業務",
                data.services.filter((s) => s.active),
              )}
              {input("date", "訪問日", "date", true)}
              {input("start", "開始時刻", "time", true)}
              {input("duration", "所要時間（分）", "number", true)}
              {input("people", "必要人数", "number", true)}
              {picks(
                "staff_ids",
                "担当者（複数選択できます）",
                data.staff.filter((p) => p.active),
              )}
              <Field label="管理用メモ" wide>
                <textarea
                  value={form.note}
                  onChange={(e) => set("note", e.target.value)}
                />
              </Field>
            </>
          )}
          {row && kind !== "visits" && (
            <label className="check">
              <input
                type="checkbox"
                checked={form.active}
                onChange={(e) => set("active", e.target.checked)}
              />
              有効
            </label>
          )}
        </fieldset>
        {kind === "visits" && row && (
          <div className="status-actions">
            <span className={"status " + row.status}>
              {statuses[row.status]}
            </span>
            {row.status === "draft" && (
              <button
                type="button"
                className="button secondary"
                disabled={busy || dirty}
                onClick={() => transition("confirm")}
              >
                確定してメンバーへ公開
              </button>
            )}
            {row.status === "confirmed" && (
              <>
                <button
                  type="button"
                  className="button secondary"
                  disabled={busy}
                  onClick={() => transition("reopen")}
                >
                  再調整へ戻す
                </button>
                <button
                  type="button"
                  className="button secondary"
                  disabled={busy}
                  onClick={() => transition("complete")}
                >
                  訪問を完了
                </button>
              </>
            )}
            {["draft", "confirmed"].includes(row.status) && (
              <button
                type="button"
                className="button subtle"
                disabled={busy}
                onClick={() => transition("cancel")}
              >
                訪問を中止
              </button>
            )}
          </div>
        )}
        {dirty && kind === "visits" && row && (
          <p className="hint">
            変更内容を保存してから、予定を確定してください。
          </p>
        )}
        <div className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            閉じる
          </button>
          {editable && (
            <Submit
              busy={busy}
              text={kind === "visits" ? "仮予定として保存" : "保存する"}
            />
          )}
        </div>
      </form>
    </Modal>
  );
}

export function SmallForm({
  title,
  fields,
  initial = {},
  onClose,
  onSubmit,
}: {
  title: string;
  fields: {
    key: string;
    label: string;
    type?: string;
    options?: { id: string; name: string }[];
  }[];
  initial?: Record<string, any>;
  onClose: () => void;
  onSubmit: (data: Record<string, any>) => Promise<unknown>;
}) {
  const [form, setForm] = useState<Record<string, any>>(initial),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [result, setResult] = useState("");
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res: any = await onSubmit(form);
      if (res?.setup_token)
        setResult(
          `${location.origin}/#setup=${encodeURIComponent(res.setup_token)}`,
        );
      else onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title={title} onClose={onClose}>
      <ErrorBox message={error} />
      {result ? (
        <>
          <p>初回設定リンクを本人へ案内してください。有効期限は24時間です。</p>
          <textarea readOnly value={result} aria-label="初回設定リンク" />
          <button
            className="button primary"
            onClick={() =>
              void navigator.clipboard
                .writeText(result)
                .then(() => setError("コピーしました"))
                .catch(() => setError("リンクを選択してコピーしてください"))
            }
          >
            リンクをコピー
          </button>
        </>
      ) : (
        <form onSubmit={save}>
          <div className="form-grid">
            {fields.map((f) => (
              <Field key={f.key} label={f.label} wide>
                {f.options ? (
                  <select
                    required
                    value={form[f.key] || ""}
                    onChange={(e) =>
                      setForm({ ...form, [f.key]: e.target.value })
                    }
                  >
                    <option value="" disabled>
                      選択してください
                    </option>
                    {f.options.map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    required
                    type={f.type || "text"}
                    min={f.key === "amount" ? 0 : undefined}
                    step={f.type === "number" ? "any" : undefined}
                    value={form[f.key] ?? ""}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        [f.key]:
                          f.type === "number"
                            ? Number(e.target.value)
                            : e.target.value,
                      })
                    }
                  />
                )}
              </Field>
            ))}
          </div>
          <div className="modal-actions">
            <button
              type="button"
              className="button secondary"
              onClick={onClose}
            >
              閉じる
            </button>
            <Submit busy={busy} />
          </div>
        </form>
      )}
    </Modal>
  );
}
