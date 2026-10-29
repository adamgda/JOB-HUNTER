import { memo, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Code,
  Group,
  Stack,
  Table,
  Text,
} from "@mantine/core";

import { STATUS_COLORS, type Company, type Offer } from "../api";

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : "";
}

interface Props {
  companies: Company[];
  offers: Offer[];
  messages: Record<number, string>;
  onRefresh: (company: Company) => void;
}

function CompaniesPanel({ companies, offers, messages, onRefresh }: Props) {
  const [expanded, setExpanded] = useState<string[]>([]);

  const toggle = (domain: string) =>
    setExpanded((prev) =>
      prev.includes(domain) ? prev.filter((d) => d !== domain) : [...prev, domain]
    );

  const rows: JSX.Element[] = [];
  for (const company of companies) {
    const companyOffers = offers.filter((o) => o.company_domain === company.domain);
    const isOpen = expanded.includes(company.domain);

    rows.push(
      <Table.Tr
        key={company.id}
        onClick={() => toggle(company.domain)}
        style={{ cursor: "pointer" }}
      >
        <Table.Td w={34}>
          <Text c="dimmed" size="sm">{isOpen ? "▾" : "▸"}</Text>
        </Table.Td>
        <Table.Td>
          <Code className="mono">{company.domain}</Code>
        </Table.Td>
        <Table.Td>{company.offers_count}</Table.Td>
        <Table.Td>
          {company.new_count > 0 ? (
            <Badge size="sm" variant="light" color="blue">
              {company.new_count} nowych
            </Badge>
          ) : null}
        </Table.Td>
        <Table.Td onClick={(e) => e.stopPropagation()}>
          <Button size="compact-xs" variant="light" onClick={() => onRefresh(company)}>
            Odśwież
          </Button>
        </Table.Td>
      </Table.Tr>
    );

    if (isOpen) {
      rows.push(
        <Table.Tr key={`${company.id}-details`}>
          <Table.Td colSpan={5} style={{ background: "rgba(0,0,0,0.15)" }}>
            <Box p="sm">
              {companyOffers.length === 0 ? (
                <Text c="dimmed" size="sm">
                  brak ofert — kliknij „Odśwież”, aby wejść na stronę kariery firmy
                </Text>
              ) : (
                <Stack gap={6}>
                  {companyOffers.map((offer) => (
                    <Group
                      key={offer.id}
                      justify="space-between"
                      gap="sm"
                      wrap="nowrap"
                      style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
                      pb={6}
                    >
                      <a href={offer.url} target="_blank" rel="noreferrer">
                        <Text size="sm">{offer.title || offer.url}</Text>
                      </a>
                      <Group gap="xs" wrap="nowrap">
                        <Text size="xs" c="dimmed">{formatDate(offer.first_seen)}</Text>
                        <Badge
                          size="sm"
                          variant="light"
                          color={STATUS_COLORS[offer.status]}
                        >
                          {offer.status}
                        </Badge>
                      </Group>
                    </Group>
                  ))}
                </Stack>
              )}
            </Box>
          </Table.Td>
        </Table.Tr>
      );
    }
  }

  if (companies.length === 0) {
    return <Text c="dimmed" size="sm">Brak firm — pojawią się po pierwszym wyszukiwaniu.</Text>;
  }

  return (
    <Stack gap="sm">
      <Text c="dimmed" size="sm">
        Kliknij wiersz (rozwiń ▸), aby zobaczyć ogłoszenia przypisane do firmy.
        „Odśwież" wchodzi bezpośrednio na stronę kariery firmy i wyciąga oferty
        (JSON-LD JobPosting + linki) — niezależnie od wyszukiwarek.
      </Text>
      <Table.ScrollContainer minWidth={700}>
        <Table verticalSpacing="xs" withTableBorder highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th w={34}></Table.Th>
              <Table.Th>Domena</Table.Th>
              <Table.Th>Oferty</Table.Th>
              <Table.Th>Nowe</Table.Th>
              <Table.Th>Akcje</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>{rows}</Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {Object.entries(messages).map(([companyId, message]) => (
        <Text key={companyId} size="xs" c="dimmed">
          {message}
        </Text>
      ))}
    </Stack>
  );
}

export default memo(CompaniesPanel);