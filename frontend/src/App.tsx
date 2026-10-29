import { useCallback, useEffect, useState } from "react";
import { Alert, AppShell, Badge, Burger, Button, Code, Group, Tabs, Text, Title } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";

import {
  api,
  type Company,
  type EngineKey,
  type HealthInfo,
  type Offer,
  type QueryLogEntry,
  type SearchBody,
  type SearchResponse,
  type Status,
} from "./api";
import type { SearchFormValues } from "./components/SearchForm";
import SearchForm, { DEFAULT_FORM } from "./components/SearchForm";
import OffersTable from "./components/OffersTable";
import CompaniesPanel from "./components/CompaniesPanel";
import QueriesPanel from "./components/QueriesPanel";
import StatsCards from "./components/StatsCards";

function parseList(text: string, separator: RegExp): string[] {
  return text
    .split(separator)
    .map((part) => part.trim())
    .filter(Boolean);
}

const sleepMs = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const SETTINGS_KEY = "jobhunter.settings.v1";
const TAB_KEY = "jobhunter.tab";

function loadForm(): SearchFormValues {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<SearchFormValues> & { exclude?: string };
      delete parsed.exclude; // sprzątanie po starym formacie (wykluczenia są teraz w DB)
      return { ...DEFAULT_FORM, ...parsed };
    }
  } catch {
    /* uszkodzony zapis — start z domyślnych */
  }
  return DEFAULT_FORM;
}

export function normalizeDomain(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .replace(/^www\./, "")
    .replace(/\/.*$/, "");
}

export default function App() {
  const [opened, { toggle }] = useDisclosure(true);
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [form, setForm] = useState<SearchFormValues>(loadForm);
  const [searching, setSearching] = useState(false);
  const [searchMsg, setSearchMsg] = useState<string | null>(null);
  const [lastSearch, setLastSearch] = useState<SearchResponse | null>(null);
  const [offers, setOffers] = useState<Offer[]>([]);
  const [offerTotal, setOfferTotal] = useState(0);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyMsg, setCompanyMsg] = useState<Record<number, string>>({});
  const [queryLog, setQueryLog] = useState<QueryLogEntry[]>([]);
  const [tab, setTab] = useState(() => {
    try {
      return localStorage.getItem(TAB_KEY) ?? "oferty";
    } catch {
      return "oferty";
    }
  });
  const [backendDown, setBackendDown] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [progressMsg, setProgressMsg] = useState<string | null>(null);
  const [exclusions, setExclusions] = useState<string[]>([]);
  const [exclusionNote, setExclusionNote] = useState<string | null>(null);

  const loadOffers = useCallback(async () => {
    const data = await api.offers(new URLSearchParams({ limit: "500" }));
    setOffers(data.items);
    setOfferTotal(data.total);
  }, []);

  const loadCompanies = useCallback(async () => {
    setCompanies((await api.companies()).items);
  }, []);

  const loadQueryLog = useCallback(async () => {
    setQueryLog((await api.queries(30)).items);
  }, []);

  const loadAll = useCallback(async () => {
    await Promise.all([loadOffers(), loadCompanies(), loadQueryLog()]);
  }, [loadOffers, loadCompanies, loadQueryLog]);

  const changeTab = (value: string | null) => {
    const next = value ?? "oferty";
    setTab(next);
    try {
      localStorage.setItem(TAB_KEY, next);
    } catch {
      /* nic */
    }
  };

  const connect = useCallback(async () => {
    try {
      await api.health().then(setHealth);
      await loadAll();
      const excluded = await api.exclusions();
      setExclusions(excluded.items);
      setBackendDown(false);
    } catch {
      setBackendDown(true);
    }
  }, [loadAll]);

  useEffect(() => {
    connect().catch(() => {});
  }, [connect]);

  useEffect(() => {
    if (!searching) {
      setElapsed(0);
      return;
    }
    const interval = setInterval(() => setElapsed((seconds) => seconds + 1), 1000);
    return () => clearInterval(interval);
  }, [searching]);

  const patchForm = (patch: Partial<SearchFormValues>) =>
    setForm((prev) => {
      const next = { ...prev, ...patch };
      try {
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(next));
      } catch {
        /* brak localStorage — ustawienia niepretrwają, aplikacja działa */
      }
      return next;
    });

  // wykluczenia: pełny zapis w bazie; zmiana z UI → POST (dodanie + natychmiastowe
  // przecięcie wpisów) albo DELETE (usunięcie kwerendy z listy)
  const syncExclusions = useCallback(
    async (next: string[]) => {
      const wanted = Array.from(new Set(next.map(normalizeDomain).filter(Boolean)));
      const removedList = exclusions.filter((d) => !wanted.includes(d));
      const addedList = wanted.filter((d) => !exclusions.includes(d));
      setExclusions(wanted);
      for (const d of removedList) await api.deleteExclusion(d).catch(() => {});
      for (const d of addedList) await api.addExclusion(d).catch(() => {});
      await loadAll().catch(() => {});
    },
    [exclusions, loadAll]
  );

  const excludeDomainRow = useCallback(
    async (offer: Offer) => {
      const domain = normalizeDomain(offer.company_domain);
      try {
        const result = await api.addExclusion(domain);
        setExclusions((prev) => (prev.includes(domain) ? prev : [...prev, domain].sort()));
        setExclusionNote(
          `wykluczono ${domain} — usunięto ${result.pruned_offers} ${result.pruned_offers === 1 ? "ofertę" : "ofert"}`
        );
        setOffers((prev) => prev.filter((o) => normalizeDomain(o.company_domain) !== domain));
        await loadAll().catch(() => {});
      } catch (error) {
        setExclusionNote(`błąd wykluczania ${domain}: ${(error as Error).message}`);
      }
    },
    [loadAll]
  );

  const runSearch = async () => {
    setSearching(true);
    setSearchMsg(null);
    setProgressMsg(null);
    setExclusionNote(null);
    try {
      const engines = (Object.keys(form.engineToggles) as EngineKey[]).filter(
        (key) => form.engineToggles[key]
      );
      if (engines.length === 0) throw new Error("Zaznacz przynajmniej jeden silnik wyszukiwania.");
      const body: SearchBody = {
        keywords: parseList(form.keywords, /\n|,|;/),
        cities: parseList(form.cities, /\n|,|;/),
        engines,
        tld: form.tld === "" ? null : form.tld,
        max_queries: form.maxQueries,
        date_restrict: form.freshness || null,
        auto_crawl: form.autoCrawl,
        crawl_max_companies: form.autoCrawl ? form.crawlMax : 0,
      };
      const started = await api.search(body);
      let status = await api.searchStatus(started.search_id);
      while (status.status === "running") {
        if (status.progress) {
          const p = status.progress;
          setProgressMsg(
            `zakończone zapytania: ${p.done} · silnik: ${p.engine} · wyniki: ${p.results_seen} · nowe: ${p.new_offers}`
          );
        }
        await sleepMs(1200);
        status = await api.searchStatus(started.search_id);
      }
      if (status.status === "error") {
        setSearchMsg(`Błąd wyszukiwania: ${status.error ?? "nieznany"}`);
        return;
      }
      const response = status.result;
      if (!response) throw new Error("Backend nie zwrócił podsumowania wyszukiwania.");
      setLastSearch(response);
      const fails = response.queries_executed
        .filter((entry) => entry.error)
        .map((entry) => `${entry.engine}: ${entry.error}`);
      const crawlNew = response.crawl.reduce((sum, entry) => sum + entry.new_offers, 0);
      const summary =
        `silniki: ${engines.join(", ")} · zapytań: ${response.queries_executed.length} · ` +
        `wyników: ${response.results_seen} · nowych: ${response.new_offers} (crawl: ${crawlNew}) · ` +
        `duplikaty: ${response.duplicates}`;
      const extras: string[] = [];
      if (fails.length) extras.push(`BŁĘDY: ${fails.join(" | ")}`);
      if (response.crawl_skipped) extras.push(response.crawl_skipped);
      if (response.pruned_offers) extras.push(`wyczyszczono (wykluczenia): ${response.pruned_offers} ofert`);
      setSearchMsg(extras.length ? `${summary} · ${extras.join(" · ")}` : summary);
      setTab("oferty");
      await loadAll();
    } catch (error) {
      const message = (error as Error).message;
      if (message.includes("Failed to fetch")) setBackendDown(true);
      setSearchMsg(`Błąd: ${message}`);
    } finally {
      setSearching(false);
      setProgressMsg(null);
    }
  };

  const setStatus = useCallback(
    async (offer: Offer, status: Status) => {
      setOffers((prev) => prev.map((o) => (o.id === offer.id ? { ...o, status } : o)));
      try {
        await api.updateOffer(offer.id, { status });
        await loadCompanies();
      } catch (error) {
        console.error(error);
        await loadOffers().catch(() => {});
      }
    },
    [loadCompanies, loadOffers]
  );

  const saveNotes = useCallback(
    async (offer: Offer, notes: string) => {
      setOffers((prev) => prev.map((o) => (o.id === offer.id ? { ...o, notes } : o)));
      try {
        await api.updateOffer(offer.id, { notes });
      } catch (error) {
        console.error(error);
        await loadOffers().catch(() => {});
      }
    },
    [loadOffers]
  );

  const removeOffer = useCallback(
    async (offer: Offer) => {
      setOffers((prev) => prev.filter((o) => o.id !== offer.id));
      setOfferTotal((prev) => Math.max(0, prev - 1));
      try {
        await api.deleteOffer(offer.id);
        await loadCompanies();
      } catch (error) {
        console.error(error);
        await loadOffers().catch(() => {});
      }
    },
    [loadCompanies, loadOffers]
  );

  const refreshCompany = async (company: Company) => {
    setCompanyMsg((prev) => ({
      ...prev,
      [company.id]: `${company.domain}: sprawdzam stronę kariery…`,
    }));
    try {
      const result = await api.refreshCompany(company.id);
      const parts = [
        `kandydaci: ${result.candidates_found} · nowe: ${result.new_offers} · duplikaty: ${result.duplicates}`,
      ];
      if (result.errors.length) parts.push(`błędy: ${result.errors.join(" | ")}`);
      setCompanyMsg((prev) => ({ ...prev, [company.id]: `${company.domain}: ${parts.join(" · ")}` }));
      await loadAll();
    } catch (error) {
      setCompanyMsg((prev) => ({
        ...prev,
        [company.id]: `${company.domain}: błąd — ${(error as Error).message}`,
      }));
    }
  };

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 350, breakpoint: "md", collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap" w="100%">
          <Group gap="sm" wrap="nowrap">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <div>
              <Title order={4} mb={0}>JOB-HUNTER</Title>
              <Text size="xs" c="dimmed" lh={1.1}>oferty poza jobboardami</Text>
            </div>
          </Group>
          <Group gap="xs" wrap="nowrap">
            <Badge variant="light" color="green">
              {`silniki: ${(Object.keys(form.engineToggles) as EngineKey[])
                .filter((key) => form.engineToggles[key])
                .length}`}
            </Badge>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md">
        <SearchForm
          values={form}
          onChange={patchForm}
          onSubmit={runSearch}
          searching={searching}
          elapsedSeconds={elapsed}
          msg={searchMsg}
          progressMsg={progressMsg}
          exclusions={exclusions}
          onExclusionsChange={(next) => syncExclusions(next).catch(() => {})}
        />
      </AppShell.Navbar>

      <AppShell.Main>
        {backendDown && (
          <Alert
            color="red"
            variant="light"
            title="Brak połączenia z backendem"
            mb="md"
          >
            <Text size="sm">
              Nie mogę pobrać danych z <Code>http://127.0.0.1:8000</Code>. Uruchom aplikację za
              pomocą <Code>./scripts/start.sh</Code>, a następnie kliknij „Ponów próbę".
            </Text>
            <Button size="xs" variant="light" mt="sm" onClick={() => connect().catch(() => {})}>
              Ponów próbę
            </Button>
          </Alert>
        )}
        <StatsCards
          offersCount={offerTotal}
          companiesCount={companies.length}
          newInLast={lastSearch?.new_offers ?? null}
        />

        <Tabs value={tab} onChange={(value) => changeTab(value)} mt="md">
          <Tabs.List>
            <Tabs.Tab value="oferty">Oferty ({offerTotal})</Tabs.Tab>
            <Tabs.Tab value="firmy">Firmy ({companies.length})</Tabs.Tab>
            <Tabs.Tab value="zapytania">Zapytania</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="oferty" pt="md">
            <OffersTable
              offers={offers}
              total={offerTotal}
              onStatus={setStatus}
              onNotes={saveNotes}
              onRemove={removeOffer}
              onExcludeDomain={excludeDomainRow}
              exclusionNote={exclusionNote}
            />
          </Tabs.Panel>

          <Tabs.Panel value="firmy" pt="md">
            <CompaniesPanel
              companies={companies}
              offers={offers}
              messages={companyMsg}
              onRefresh={refreshCompany}
            />
          </Tabs.Panel>

          <Tabs.Panel value="zapytania" pt="md">
            <QueriesPanel log={queryLog} lastSearch={lastSearch} />
          </Tabs.Panel>
        </Tabs>
      </AppShell.Main>
    </AppShell>
  );
}