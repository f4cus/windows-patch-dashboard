export const REPORT_STATUSES = [
  "manual-golden-fixture",
  "generated",
  "partial",
  "verified",
] as const;

export const UPDATE_TYPES = ["security", "oob", "preview", "unknown"] as const;

export const KNOWN_ISSUES_STATUSES = [
  "none",
  "open",
  "resolved",
  "not-published",
  "unknown",
] as const;

export const SOURCE_TYPES = [
  "microsoft-support",
  "msrc",
  "release-health",
] as const;

export type ReportStatus = (typeof REPORT_STATUSES)[number];
export type UpdateType = (typeof UPDATE_TYPES)[number];
export type KnownIssuesStatus = (typeof KNOWN_ISSUES_STATUSES)[number];
export type SourceType = (typeof SOURCE_TYPES)[number];
export type OsFamily = "Windows Server" | "Windows 11";

export interface ReportSource {
  readonly type: SourceType;
  readonly url: string;
  readonly retrievedAt?: string | null;
}

export interface OperatingSystem {
  readonly family: OsFamily;
  readonly version: string;
  readonly channel: string | null;
  readonly displayName: string;
}

export interface UpdateRecord {
  readonly kb: string;
  readonly os: OperatingSystem;
  readonly updateType: UpdateType;
  readonly releaseDate: string | null;
  readonly changesSummary: string;
  readonly resolvedIssuesSummary: string;
  readonly knownIssuesSummary: string;
  readonly knownIssuesStatus: KnownIssuesStatus;
  readonly supersededBy: string | null;
  readonly sources: readonly ReportSource[];
}

export interface MonthlyReport {
  readonly schemaVersion: "1.0.0";
  readonly reportMonth: string;
  readonly patchTuesdayDate: string;
  readonly generatedAt: string | null;
  readonly status: ReportStatus;
  readonly updates: readonly UpdateRecord[];
}
