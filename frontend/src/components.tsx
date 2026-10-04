import { useEffect, useRef, type ReactNode } from "react";
import { House, X, LoaderCircle } from "lucide-react";
export function Brand() {
  return (
    <div className="brand">
      <span className="brand-icon">
        <House size={26} />
      </span>
      <div>
        訪問のアトリエ<small>CARE ATELIER</small>
      </div>
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    const old = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = old;
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={"modal " + (wide ? "wide" : "")}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <div className="modal-head">
        <div>
          <small className="eyebrow">CARE ATELIER</small>
          <h2>{title}</h2>
        </div>
        <button aria-label="閉じる" className="icon-button" onClick={onClose}>
          <X />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Field({
  label,
  children,
  wide = false,
}: {
  label: string;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <label className={"field " + (wide ? "span-2" : "")}>
      <span>{label}</span>
      {children}
    </label>
  );
}
export function ErrorBox({ message }: { message: string }) {
  return message ? (
    <div className="error-box" role="alert">
      {message}
    </div>
  ) : null;
}
export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="empty">
      <House size={30} />
      <p>{children}</p>
    </div>
  );
}
export function Submit({
  busy,
  text = "保存する",
  disabled = false,
}: {
  busy: boolean;
  text?: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="submit"
      className="button primary"
      disabled={busy || disabled}
    >
      {busy ? (
        <>
          <LoaderCircle size={16} className="spin" />
          保存中…
        </>
      ) : (
        text
      )}
    </button>
  );
}
