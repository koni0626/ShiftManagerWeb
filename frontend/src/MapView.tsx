import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapPin, Navigation } from "lucide-react";
import { api, type Row } from "./api";
import { Empty } from "./components";
export default function MapView({
  clients,
  onCoordinates,
}: {
  clients: Row[];
  onCoordinates?: (row: Row) => void;
}) {
  const host = useRef<HTMLDivElement>(null),
    map = useRef<L.Map | null>(null),
    [selected, setSelected] = useState<Row | null>(null),
    [configured, setConfigured] = useState(false);
  useEffect(() => {
    const m = L.map(host.current!, { attributionControl: true }).setView(
      [35.68, 139.76],
      12,
    );
    map.current = m;
    let live = true;
    void api("/config").then((c) => {
      if (!live) return;
      if (c.tile_url) {
        L.tileLayer(c.tile_url, {
          attribution: c.attribution,
          maxZoom: 19,
        }).addTo(m);
        setConfigured(true);
      }
    });
    return () => {
      live = false;
      m.remove();
      map.current = null;
    };
  }, []);
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const group = L.featureGroup().addTo(m);
    clients
      .filter(
        (c) =>
          c.latitude != null &&
          c.longitude != null &&
          c.geocode_status === "resolved",
      )
      .forEach((c) => {
        const marker = L.marker([c.latitude, c.longitude], {
          icon: L.divIcon({
            className: "atelier-pin",
            html: "<span></span>",
            iconSize: [26, 32],
            iconAnchor: [13, 30],
          }),
        });
        marker.bindTooltip(document.createTextNode(c.label) as any);
        marker.on("click", () => setSelected(c));
        marker.addTo(group);
      });
    if (group.getLayers().length)
      m.fitBounds(group.getBounds().pad(0.18), { maxZoom: 15 });
    return () => {
      group.remove();
    };
  }, [clients]);
  return (
    <div className="map-layout">
      <section className="panel map-panel">
        <div ref={host} className="map-canvas" aria-label="訪問先の地図" />
        {!configured && (
          <p className="map-notice">
            背景地図は未設定です。保存した座標の位置を表示しています。
          </p>
        )}
      </section>
      <section className="map-list">
        {selected && (
          <article className="panel person-card">
            <span className="eyebrow">VISIT GUIDE</span>
            <h2>{selected.label}</h2>
            <p>
              {selected.address} {selected.building}
            </p>
            <p>{selected.guide || "訪問案内は未登録です。"}</p>
            {selected.phone && (
              <a href={"tel:" + selected.phone}>{selected.phone}</a>
            )}
            {selected.address && (
              <a
                className="button primary"
                target="_blank"
                rel="noreferrer"
                href={
                  "https://www.google.com/maps/dir/?api=1&destination=" +
                  encodeURIComponent(
                    selected.address + " " + (selected.building || ""),
                  )
                }
              >
                <Navigation size={16} />
                外部地図で経路を開く
              </a>
            )}
          </article>
        )}
        {clients.length === 0 && <Empty>表示できる訪問先がありません。</Empty>}
        {clients.map((c) => (
          <article
            key={c.id}
            className={
              "panel map-client " + (selected?.id === c.id ? "selected" : "")
            }
          >
            <button
              className="map-client-main"
              onClick={() => {
                setSelected(c);
                if (c.latitude != null)
                  map.current?.setView([c.latitude, c.longitude], 16);
              }}
            >
              <MapPin size={19} />
              <div>
                <strong>{c.label}</strong>
                <small>{c.address || "住所未登録"}</small>
                <span
                  className={
                    "status " +
                    (c.geocode_status === "resolved" ? "confirmed" : "draft")
                  }
                >
                  {(
                    {
                      resolved: "位置設定済み",
                      queued: "位置を取得中",
                      running: "位置を取得中",
                      failed: "位置取得に失敗",
                      needs_review: "位置の確認が必要",
                      not_found: "該当なし",
                    } as Record<string, string>
                  )[c.geocode_status] || "位置未設定"}
                </span>
              </div>
            </button>
            {onCoordinates && (
              <button
                className="button subtle"
                onClick={() => onCoordinates(c)}
              >
                位置を設定
              </button>
            )}
          </article>
        ))}
      </section>
    </div>
  );
}
