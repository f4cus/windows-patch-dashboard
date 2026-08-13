import type { MonthlyReport } from "./model";
import { loadMonthlyReport } from "./loadMonthlyReport";

type RawReportModules = Readonly<Record<string, unknown>>;

interface CatalogEntry {
  readonly path: string;
  readonly report: MonthlyReport;
  readonly priority: number;
}

function sourcePriority(path: string): number {
  return path.replaceAll("\\", "/").includes("/data/reports/") ? 2 : 1;
}

export function createReportCatalog(
  rawModules: RawReportModules,
): readonly MonthlyReport[] {
  const reportsByMonth = new Map<string, CatalogEntry>();

  for (const [path, rawReport] of Object.entries(rawModules)) {
    const report = loadMonthlyReport(rawReport);
    const priority = sourcePriority(path);
    const existing = reportsByMonth.get(report.reportMonth);

    if (existing !== undefined && existing.priority === priority) {
      throw new Error(
        `Duplicate local report month ${report.reportMonth}: ${existing.path} and ${path}`,
      );
    }

    if (existing === undefined || priority > existing.priority) {
      reportsByMonth.set(report.reportMonth, { path, report, priority });
    }
  }

  return [...reportsByMonth.values()]
    .map(({ report }) => report)
    .sort((left, right) => right.reportMonth.localeCompare(left.reportMonth));
}

const rawReportModules = import.meta.glob(
  ["../../../data/fixtures/*.json", "../../../data/reports/*.json"],
  { eager: true, import: "default" },
) as RawReportModules;

export const localReports = createReportCatalog(rawReportModules);
