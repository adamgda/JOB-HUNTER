import { memo } from "react";
import { Alert, Badge, Code, List, ListItem, Stack, Table, Text } from "@mantine/core";

import type { SearchResponse, QueryLogEntry } from "../api";

interface Props {
  log: QueryLogEntry[];
  lastSearch: SearchResponse | null;
}

function QueriesPanel({ log, lastSearch }: Props) {
  return (
    <Stack gap="md">
      {lastSearch && (
        <Alert color="violet" variant="light" title="Ostatnie wyszukiwanie">
          <Text size="sm">
            {lastSearch.queries_executed.length} zapytań · wyników: {lastSearch.results_seen} ·
            nowe: {lastSearch.new_offers} · duplikaty: {lastSearch.duplicates}
          </Text>
          {lastSearch.crawl.length > 0 && (
            <>
              <Text size="sm" fw={600} mt="sm">Crawl stron kariery:</Text>
              <List size="sm" spacing="xs">
                {lastSearch.crawl.map((entry) => (
                  <ListItem key={entry.company}>
                    <Text size="sm">
                      <Code className="mono">{entry.company}</Code> — kandydaci:{" "}
                      {entry.candidates_found}, nowe: <b>{entry.new_offers}</b>
                      {entry.errors.length > 0 && `, błędy: ${entry.errors.join(" | ")}`}
                    </Text>
                  </ListItem>
                ))}
              </List>
            </>
          )}
        </Alert>
      )}

      <Table.ScrollContainer minWidth={700}>
        <Table verticalSpacing="xs" withTableBorder highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Kiedy</Table.Th>
              <Table.Th>Silnik</Table.Th>
              <Table.Th>Wyniki</Table.Th>
              <Table.Th>Zapytanie</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {log.map((entry) => (
              <Table.Tr key={entry.id}>
                <Table.Td w={150}>
                  <Text size="xs" c="dimmed">{entry.created_at}</Text>
                </Table.Td>
                <Table.Td w={110}>
                  <Badge size="sm" variant="light" color="violet">{entry.engine}</Badge>
                </Table.Td>
                <Table.Td w={70}>
                  {entry.http_status ? entry.results_count : "błąd"}
                </Table.Td>
                <Table.Td>
                  <Code className="mono wrap-anywhere">{entry.query}</Code>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Stack>
  );
}

export default memo(QueriesPanel);