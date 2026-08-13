import type { MonthlyReport, UpdateRecord } from "./model";

const SERVER_ORDER = new Map<string, number>([
  ["Windows Server 2012 (ESU)", 0],
  ["Windows Server 2012 R2 (ESU)", 1],
  ["Windows Server 2016", 2],
  ["Windows Server 2019", 3],
  ["Windows Server 2022", 4],
  ["Windows Server, version 23H2", 5],
  ["Windows Server 2025", 6],
]);

interface SortableUpdate {
  readonly update: UpdateRecord;
  readonly originalIndex: number;
}

function compareText(left: string, right: string): number {
  if (left === right) {
    return 0;
  }

  return left < right ? -1 : 1;
}

function windows11BranchOrder(version: string | null | undefined): number {
  if (version === null || version === undefined) {
    return Number.MAX_SAFE_INTEGER;
  }

  const branch = /(?:^|\D)(\d{2})H([12])(?:\D|$)/u.exec(version);
  if (branch === null) {
    return Number.MAX_SAFE_INTEGER;
  }

  return Number.parseInt(branch[1], 10) * 2 + Number.parseInt(branch[2], 10);
}

function osOrder(update: UpdateRecord): readonly [number, number, string] {
  if (update.os.family === "Windows Server") {
    return [
      0,
      SERVER_ORDER.get(update.os.displayName) ?? Number.MAX_SAFE_INTEGER,
      update.os.displayName,
    ];
  }

  return [
    1,
    windows11BranchOrder(update.os.version),
    update.os.version ?? update.os.displayName,
  ];
}

function compareUpdates(left: SortableUpdate, right: SortableUpdate): number {
  const leftOs = osOrder(left.update);
  const rightOs = osOrder(right.update);

  const familyComparison = leftOs[0] - rightOs[0];
  if (familyComparison !== 0) {
    return familyComparison;
  }

  const branchComparison = leftOs[1] - rightOs[1];
  if (branchComparison !== 0) {
    return branchComparison;
  }

  const versionComparison = compareText(leftOs[2], rightOs[2]);
  if (versionComparison !== 0) {
    return versionComparison;
  }

  const dateComparison = compareText(
    left.update.releaseDate ?? "",
    right.update.releaseDate ?? "",
  );
  if (dateComparison !== 0) {
    return dateComparison;
  }

  const typeComparison = compareText(
    left.update.updateType,
    right.update.updateType,
  );
  if (typeComparison !== 0) {
    return typeComparison;
  }

  const kbComparison = compareText(left.update.kb, right.update.kb);
  return kbComparison !== 0
    ? kbComparison
    : left.originalIndex - right.originalIndex;
}

export function sortUpdates(
  updates: readonly UpdateRecord[],
): readonly UpdateRecord[] {
  return updates
    .map((update, originalIndex) => ({ update, originalIndex }))
    .sort(compareUpdates)
    .map(({ update }) => update);
}

export function sortMonthlyReport(report: MonthlyReport): MonthlyReport {
  return {
    ...report,
    updates: sortUpdates(report.updates),
  };
}
