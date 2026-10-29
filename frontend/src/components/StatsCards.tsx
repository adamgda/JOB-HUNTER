import { memo } from "react";
import { Card, SimpleGrid, Text, Title } from "@mantine/core";

interface Props {
  offersCount: number;
  companiesCount: number;
  newInLast?: number | null;
}

function StatCard({ value, label, sub }: { value: string; label: string; sub?: string }) {
  return (
    <Card withBorder radius="md" padding="md">
      <Title order={3}>{value}</Title>
      <Text c="dimmed" size="sm">{label}</Text>
      {sub && <Text size="xs" c="dimmed">{sub}</Text>}
    </Card>
  );
}

function StatsCards({ offersCount, companiesCount, newInLast }: Props) {
  return (
    <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="md">
      <StatCard value={String(offersCount)} label="ofert w bazie" />
      <StatCard value={String(companiesCount)} label="firm w bazie" />
      <StatCard
        value={newInLast != null ? String(newInLast) : "–"}
        label="nowych (ostatnie wyszukiwanie)"
      />
    </SimpleGrid>
  );
}

export default memo(StatsCards);