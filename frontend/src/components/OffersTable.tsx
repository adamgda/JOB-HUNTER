import { memo, useMemo, useState } from "react";
import { Group, Pagination, Select, Stack, Table, Text, TextInput } from "@mantine/core";

import { STATUSES, TEXT_LANG_LABELS, type Offer, type Status } from "../api";

const PAGE_SIZE = 50;

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : "";
}

interface Props {
  offers: Offer[];
  total: number;
  onStatus: (offer: Offer, status: Status) => void;
  onNotes: (offer: Offer, notes: string) => void;
  onRemove: (offer: Offer) => void;
  onExcludeDomain: (offer: Offer) => void;
  exclusionNote: string | null;
}

function OffersTable({ offers, total, onStatus, onNotes, onRemove, onExcludeDomain, exclusionNote }: Props) {
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [langFilter, setLangFilter] = useState<string | null>(null);
  const [textLangFilter, setTextLangFilter] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const langOptions = useMemo(() => {
    const counts = new Map<string, number>();
    for (const offer of offers) {
      for (const lang of (offer.languages ?? "").split(",").map((x) => x.trim()).filter(Boolean)) {
        counts.set(lang, (counts.get(lang) ?? 0) + 1);
      }
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([name, count]) => ({ value: name, label: `${name} (${count})` }));
  }, [offers]);

  const textLangOptions = useMemo(() => {
    const counts = new Map<string, number>();
    for (const offer of offers) {
      const code = offer.text_lang ?? "unknown";
      counts.set(code, (counts.get(code) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([code, count]) => ({
        value: code,
        label: `${TEXT_LANG_LABELS[code] ?? code} (${count})`,
      }));
  }, [offers]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return offers.filter((offer) => {
      if (statusFilter && offer.status !== statusFilter) return false;
      if (langFilter) {
        const langs = (offer.languages ?? "").toLowerCase().split(",").map((x) => x.trim());
        if (!langs.includes(langFilter.toLowerCase())) return false;
      }
      if (textLangFilter && (offer.text_lang ?? "unknown") !== textLangFilter) return false;
      if (!needle) return true;
      return (
        offer.title.toLowerCase().includes(needle) ||
        offer.company_domain.toLowerCase().includes(needle) ||
        offer.url.toLowerCase().includes(needle)
      );
    });
  }, [offers, q, statusFilter, langFilter, textLangFilter]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const visible = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  return (
    <Stack gap="sm">
      <Group justify="space-between" gap="sm" wrap="wrap">
        <TextInput
          style={{ flex: 1, minWidth: 220 }}
          placeholder="Filtruj: tytuł / firma / URL…"
          value={q}
          onChange={(event) => {
            setQ(event.currentTarget.value);
            setPage(1);
          }}
        />
        <Select
          style={{ width: 170 }}
          placeholder="wszystkie statusy"
          clearable
          data={STATUSES.map((s) => ({ value: s, label: s }))}
          value={statusFilter}
          onChange={(value) => {
            setStatusFilter(value ?? null);
            setPage(1);
          }}
        />
        <Select
          style={{ width: 190 }}
          placeholder="język: wszystkie"
          clearable
          data={langOptions}
          value={langFilter}
          onChange={(value) => {
            setLangFilter(value ?? null);
            setPage(1);
          }}
        />
        <Select
          style={{ width: 185 }}
          placeholder="treść: wszystkie języki"
          clearable
          data={textLangOptions}
          value={textLangFilter}
          onChange={(value) => {
            setTextLangFilter(value ?? null);
            setPage(1);
          }}
        />
      </Group>

      {exclusionNote && <Text size="sm" c="orange.4">{exclusionNote}</Text>}

      {visible.length === 0 ? (
        <Text c="dimmed" size="sm">
          Pusto — uruchom wyszukiwanie w panelu po lewej albo zmień/zdejmij filtry.
        </Text>
      ) : (
        <Table.ScrollContainer minWidth={980}>
          <Table verticalSpacing="xs" horizontalSpacing="sm" withTableBorder>
            <thead className="thead">
              <tr>
                <th>Firma</th>
                <th>Oferta / strona</th>
                <th>Źródło</th>
                <th>Pobrane</th>
                <th>Status</th>
                <th>Notatka</th>
                <th>Akcje</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((offer) => (
                <tr key={offer.id}>
                  <td style={{ width: 150 }}>
                    <code className="mono">{offer.company_domain}</code>
                  </td>
                  <td>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        flexWrap: "wrap",
                      }}
                    >
                      <a href={offer.url} target="_blank" rel="noreferrer">
                        {offer.title || offer.url}
                      </a>
                      {(offer.languages ?? "")
                        .split(",")
                        .slice(0, 2)
                        .filter(Boolean)
                        .map((lang) => (
                          <span key={lang} className="chip">{lang.trim()}</span>
                        ))}
                      {(offer.text_lang ?? "unknown") !== "unknown" && (
                        <span
                          className="chip lang"
                          title={`treść: ${TEXT_LANG_LABELS[offer.text_lang] ?? offer.text_lang}`}
                        >
                          {offer.text_lang.toUpperCase()}
                        </span>
                      )}
                    </div>
                    {(offer.location || offer.salary) && (
                      <div className="dimmed" style={{ marginTop: 3 }}>
                        {[offer.location, offer.salary].filter(Boolean).join(" · ")}
                      </div>
                    )}
                  </td>
                  <td className="dimmed">{offer.source}</td>
                  <td>
                    <span className="dimmed">{formatDate(offer.first_seen)}</span>
                  </td>
                  <td>
                    <select
                      className={`native-status s-${offer.status}`}
                      value={offer.status}
                      onChange={(event) => onStatus(offer, event.target.value as Status)}
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      className="native-notes"
                      defaultValue={offer.notes ?? ""}
                      placeholder="np. wysłano CV 12.03"
                      onBlur={(event) => {
                        if (event.target.value !== (offer.notes ?? "")) {
                          onNotes(offer, event.target.value);
                        }
                      }}
                    />
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button className="btn-row danger" onClick={() => onRemove(offer)}>
                        Usuń
                      </button>
                      <button
                        className="btn-row warn"
                        title={`dodaj ${offer.company_domain} do wykluczeń`}
                        onClick={() => onExcludeDomain(offer)}
                      >
                        Wyklucz
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      <Group justify="space-between">
        <Text c="dimmed" size="sm">
          {filtered.length} z {total} ofert · strona {safePage}/{pageCount}
        </Text>
        <Pagination
          value={safePage}
          onChange={setPage}
          total={pageCount}
          size="sm"
          siblings={1}
          boundaries={1}
        />
      </Group>
    </Stack>
  );
}

export default memo(OffersTable);