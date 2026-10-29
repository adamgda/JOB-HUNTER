export type Status = "nowa" | "obejrzana" | "aplikowano" | "odrzucona";

export const STATUSES: Status[] = ["nowa", "obejrzana", "aplikowano", "odrzucona"];

export const STATUS_COLORS: Record<Status, string> = {
  nowa: "blue",
  obejrzana: "gray",
  aplikowano: "green",
  odrzucona: "red",
};

export const TEXT_LANG_LABELS: Record<string, string> = {
  pl: "polski",
  en: "angielski",
  de: "niemiecki",
  uk: "ukraiński",
  ru: "rosyjski",
  fr: "francuski",
  es: "hiszpański",
  it: "włoski",
  nl: "holenderski",
  unknown: "nieznany",
};

export type EngineKey =
  | "google_free"
  | "duckduckgo"
  | "bing"
  | "yahoo"
  | "brave"
  | "google_scrape";

export const ENGINE_LABELS: Record<EngineKey, string> = {
  google_free: "Google (darmowy, przez ddgs)",
  duckduckgo: "DuckDuckGo",
  bing: "Bing",
  yahoo: "Yahoo",
  brave: "Brave",
  google_scrape: "Google scraping (awaryjny)",
};

export interface Offer {
  id: number;
  company_id: number;
  company_domain: string;
  title: string;
  url: string;
  location: string | null;
  salary: string | null;
  languages: string;
  text_lang: string;
  source: string;
  source_query: string | null;
  first_seen: string;
  last_seen: string;
  status: Status;
  notes: string | null;
}

export interface Company {
  id: number;
  domain: string;
  name: string | null;
  first_seen: string;
  last_seen: string;
  offers_count: number;
  new_count: number;
}

export interface HealthInfo {
  status: string;
  db: string;
}

export interface QueryEntry {
  query: string | null;
  engine: string;
  results_count?: number;
  new_offers?: number;
  duplicates?: number;
  skipped_excluded?: number;
  error?: string | null;
  skipped?: string;
}

export interface CrawlEntry {
  company: string;
  career_url: string | null;
  candidates_found: number;
  new_offers: number;
  duplicates: number;
  errors: string[];
}

export interface SearchResponse {
  queries_executed: QueryEntry[];
  results_seen: number;
  new_offers: number;
  duplicates: number;
  skipped_excluded: number;
  pruned_offers?: number;
  crawl: CrawlEntry[];
  crawl_skipped?: string | null;
}

export interface SearchProgress {
  done: number;
  engine: string;
  query: string;
  new_offers: number;
  results_seen: number;
  duplicates: number;
}

export interface SearchStartResponse {
  search_id: string;
  started: boolean;
  already_running: boolean;
}

export interface SearchSnapshot {
  search_id: string;
  status: "running" | "done" | "error";
  elapsed: number;
  progress?: SearchProgress | null;
  result?: SearchResponse | null;
  error?: string | null;
}

export interface QueryLogEntry {
  id: number;
  query: string;
  engine: string;
  results_count: number;
  http_status: number | null;
  created_at: string;
}

export interface SearchBody {
  keywords: string[];
  cities?: string[];
  exclude?: string[];
  engines: EngineKey[];
  tld?: string | null;
  max_queries?: number;
  num_per_query?: number;
  date_restrict?: string | null;
  auto_crawl?: boolean;
  crawl_max_companies?: number;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const payload = await response.json();
      if (payload?.detail) detail = `${detail}: ${payload.detail}`;
    } catch {
      /* odpowiedź bez JSON */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<HealthInfo>("/api/health"),
  search: (body: SearchBody) =>
    request<SearchStartResponse>("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  searchStatus: (id: string) => request<SearchSnapshot>(`/api/search/${id}`),
  exclusions: () => request<{ items: string[] }>("/api/exclusions"),
  addExclusion: (domain: string) =>
    request<{ added: boolean; domain: string; pruned_offers: number }>("/api/exclusions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ domain }),
    }),
  deleteExclusion: (domain: string) =>
    request<{ removed: boolean; domain: string }>(`/api/exclusions/${domain}`, { method: "DELETE" }),
  offers: (params: URLSearchParams) =>
    request<{ items: Offer[]; total: number }>(`/api/offers?${params.toString()}`),
  updateOffer: (id: number, patch: { status?: Status; notes?: string }) =>
    request<Offer>(`/api/offers/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }),
  deleteOffer: (id: number) =>
    request<{ deleted: boolean; id: number }>(`/api/offers/${id}`, { method: "DELETE" }),
  companies: () => request<{ items: Company[] }>("/api/companies"),
  refreshCompany: (id: number) =>
    request<{
      career_url: string | null;
      pages_visited: string[];
      candidates_found: number;
      new_offers: number;
      duplicates: number;
      errors: string[];
    }>(`/api/companies/${id}/refresh`, { method: "POST" }),
  queries: (limit?: number) =>
    request<{ items: QueryLogEntry[] }>(`/api/queries?limit=${limit ?? 30}`),
};