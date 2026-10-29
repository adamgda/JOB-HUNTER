import {
  Alert,
  Button,
  Fieldset,
  NumberInput,
  SegmentedControl,
  Select,
  Stack,
  Switch,
  TagsInput,
  Text,
  Textarea,
  TextInput,
} from "@mantine/core";

import { ENGINE_LABELS, type EngineKey } from "../api";

export interface SearchFormValues {
  keywords: string;
  cities: string;
  tld: "pl" | "";
  freshness: "" | "d7" | "m1";
  maxQueries: number;
  autoCrawl: boolean;
  crawlMax: number;
  engineToggles: Record<EngineKey, boolean>;
}

export const DEFAULT_FORM: SearchFormValues = {
  keywords: "frontend developer\nQA engineer",
  cities: "",
  tld: "pl",
  freshness: "",
  maxQueries: 6,
  autoCrawl: true,
  crawlMax: 2,
  engineToggles: {
    google_free: true,
    duckduckgo: true,
    bing: true,
    yahoo: false,
    brave: false,
    google_scrape: false,
  },
};

interface Props {
  values: SearchFormValues;
  onChange: (patch: Partial<SearchFormValues>) => void;
  onSubmit: () => void;
  searching: boolean;
  elapsedSeconds: number;
  progressMsg: string | null;
  exclusions: string[];
  onExclusionsChange: (next: string[]) => void;
  msg: string | null;
}

export default function SearchForm({
  values,
  onChange,
  onSubmit,
  searching,
  elapsedSeconds,
  progressMsg,
  exclusions,
  onExclusionsChange,
  msg,
}: Props) {
  const toggleEngine = (key: EngineKey, checked: boolean) =>
    onChange({ engineToggles: { ...values.engineToggles, [key]: checked } });

  return (
    <Stack gap="sm">
      <Textarea
        label="Słowa kluczowe"
        description="Każda rola w osobnej linii (albo po przecinku)"
        autosize
        minRows={4}
        value={values.keywords}
        onChange={(event) => onChange({ keywords: event.currentTarget.value })}
      />
      <TextInput
        label="Miasta (opcjonalnie)"
        placeholder="Warszawa, Kraków, Wrocław…"
        value={values.cities}
        onChange={(event) => onChange({ cities: event.currentTarget.value })}
      />
      <Fieldset legend="Silniki wyszukiwania">
        <Stack gap="xs">
          {(Object.keys(ENGINE_LABELS) as EngineKey[]).map((key) => (
            <Switch
              key={key}
              size="sm"
              label={ENGINE_LABELS[key]}
              checked={values.engineToggles[key]}
              onChange={(event) => toggleEngine(key, event.currentTarget.checked)}
            />
          ))}
        </Stack>
      </Fieldset>
      <Fieldset legend="Zakres wyszukiwania">
        <Stack gap="sm">
          <div>
            <Text size="xs" c="dimmed" mb={4}>Filtr domeny (TLD)</Text>
            <SegmentedControl
              fullWidth
              value={values.tld}
              onChange={(value) => onChange({ tld: value as SearchFormValues["tld"] })}
              data={[
                { value: "pl", label: "tylko .pl" },
                { value: "", label: "wszystkie TLD" },
              ]}
            />
          </div>
          <Select
            label="Świeżość"
            data={[
              { value: "", label: "bez filtra" },
              { value: "d7", label: "ostatni tydzień" },
              { value: "m1", label: "ostatni miesiąc" },
            ]}
            value={values.freshness}
            onChange={(value) => onChange({ freshness: (value ?? "") as SearchFormValues["freshness"] })}
          />
          <NumberInput
            label="Maks. zapytań na silnik"
            min={1}
            max={30}
            value={values.maxQueries}
            onChange={(value) => onChange({ maxQueries: typeof value === "number" ? value : 8 })}
          />
          <Switch
            size="sm"
            label="Auto-crawl: wchodzenie na /kariera nowych firm"
            checked={values.autoCrawl}
            onChange={(event) => onChange({ autoCrawl: event.currentTarget.checked })}
          />
          <NumberInput
            label="Maks. firm na auto-crawl"
            min={0}
            max={5}
            disabled={!values.autoCrawl}
            value={values.crawlMax}
            onChange={(value) => onChange({ crawlMax: typeof value === "number" ? value : 2 })}
          />
        </Stack>
      </Fieldset>
      <TagsInput
        label="Wykluczone domeny"
        description="Enter/przecinek dodaje; × na chipie usuwa — lista trzymam w bazie"
        allowDuplicates={false}
        value={exclusions}
        data={[]}
        onChange={(next) => onExclusionsChange(next ?? [])}
      />
      <Button onClick={onSubmit} loading={searching} fullWidth size="md" variant="filled">
        {searching ? `Szukam… ${elapsedSeconds} s` : "Szukaj"}
      </Button>
      <Text size="xs" c="dimmed">
        Silniki mają limity: maks. 20 s na zapytanie i 75 s na całe wyszukiwanie — wyniki
        (częściowe) trafią na listę nawet przy przerwaniu.
      </Text>
      {searching && progressMsg && (
        <Text size="sm" c="blue.4">{progressMsg}</Text>
      )}
      {msg && (
        <Alert
          color={msg.startsWith("Błąd") ? "red" : "dark"}
          variant="light"
          styles={{ title: { fontWeight: 600 } }}
        >
          <Text size="sm">{msg}</Text>
        </Alert>
      )}
    </Stack>
  );
}