import {
  KNOWN_ISSUES_STATUSES,
  REPORT_STATUSES,
  SOURCE_TYPES,
  UPDATE_TYPES,
  type MonthlyReport,
  type OperatingSystem,
  type ReportStatus,
  type ReportSource,
  type SourceType,
  type UpdateRecord,
} from "./model";
import { sortMonthlyReport } from "./sortUpdates";

const REPORT_MONTH_PATTERN = /^\d{4}-(0[1-9]|1[0-2])$/u;
const DATE_PATTERN = /^\d{4}-(0[1-9]|1[0-2])-([012]\d|3[01])$/u;
const KB_PATTERN = /^(KB\d+|NO PUBLICADO)$/u;
const SUPERSEDENCE_PATTERN = /^KB\d+$/u;
const WINDOWS_11_VERSION_PATTERN = /^\d{2}H[12](?:\/\d{2}H[12])*$/u;
const WINDOWS_11_BRANCH_PATTERN = /(?<year>\d{2})H(?<half>[12])/gu;

const SERVER_IDENTITIES = new Map<
  string,
  { readonly version: string; readonly channel: string | null }
>([
  ["Windows Server 2012 (ESU)", { version: "2012", channel: "ESU" }],
  ["Windows Server 2012 R2 (ESU)", { version: "2012 R2", channel: "ESU" }],
  ["Windows Server 2016", { version: "2016", channel: null }],
  ["Windows Server 2019", { version: "2019", channel: null }],
  ["Windows Server 2022", { version: "2022", channel: null }],
  ["Windows Server 2025", { version: "2025", channel: null }],
]);

const SOURCE_HOSTS: Readonly<Record<SourceType, readonly string[]>> = {
  "microsoft-support": ["support.microsoft.com"],
  msrc: ["msrc.microsoft.com", "api.msrc.microsoft.com"],
  "release-health": ["learn.microsoft.com"],
};

export class MonthlyReportValidationError extends Error {
  constructor(message: string) {
    super(`Invalid monthly report: ${message}`);
    this.name = "MonthlyReportValidationError";
  }
}

function fail(path: string, expected: string): never {
  throw new MonthlyReportValidationError(`${path} must be ${expected}`);
}

function readObject(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return fail(path, "an object");
  }

  return value as Record<string, unknown>;
}

function readString(value: unknown, path: string): string {
  if (typeof value !== "string") {
    return fail(path, "a string");
  }

  return value;
}

function readNonEmptyString(value: unknown, path: string): string {
  const candidate = readString(value, path);
  if (candidate.length === 0) {
    return fail(path, "a non-empty string");
  }

  return candidate;
}

function readNullableString(value: unknown, path: string): string | null {
  return value === null ? null : readString(value, path);
}

function readEnum<const T extends readonly string[]>(
  value: unknown,
  allowed: T,
  path: string,
): T[number] {
  const candidate = readString(value, path);
  if (!allowed.includes(candidate)) {
    return fail(path, `one of: ${allowed.join(", ")}`);
  }

  return candidate as T[number];
}

function readDate(value: unknown, path: string): string {
  const candidate = readString(value, path);
  if (!DATE_PATTERN.test(candidate)) {
    return fail(path, "an ISO date (YYYY-MM-DD)");
  }

  return candidate;
}

function readDateTime(value: unknown, path: string): string {
  const candidate = readString(value, path);
  if (Number.isNaN(Date.parse(candidate))) {
    return fail(path, "an ISO date-time");
  }

  return candidate;
}

function readOptionalNullableDateTime(
  object: Record<string, unknown>,
  key: string,
  path: string,
): string | null | undefined {
  if (!(key in object)) {
    return undefined;
  }

  const value = object[key];
  return value === null ? null : readDateTime(value, `${path}.${key}`);
}

function readOs(value: unknown, path: string): OperatingSystem {
  const os = readObject(value, path);
  const family = readEnum(
    os.family,
    ["Windows Server", "Windows 11"] as const,
    `${path}.family`,
  );
  const displayName = readNonEmptyString(os.displayName, `${path}.displayName`);
  const version = readNonEmptyString(os.version, `${path}.version`);
  const channel = readNullableString(os.channel, `${path}.channel`);

  if (family === "Windows Server") {
    const expectedIdentity = SERVER_IDENTITIES.get(displayName);
    if (
      expectedIdentity === undefined ||
      version !== expectedIdentity.version ||
      channel !== expectedIdentity.channel
    ) {
      return fail(
        path,
        "a supported, internally consistent Windows Server identity",
      );
    }
  } else {
    if (channel !== null) {
      return fail(`${path}.channel`, "null for Windows 11");
    }
    if (
      !WINDOWS_11_VERSION_PATTERN.test(version) ||
      displayName !== `Windows 11 ${version}`
    ) {
      return fail(path, "a matching Windows 11 version and display name");
    }

    const branchOrder = [...version.matchAll(WINDOWS_11_BRANCH_PATTERN)].map(
      ({ groups }) =>
        Number.parseInt(groups?.year ?? "", 10) * 2 +
        Number.parseInt(groups?.half ?? "", 10),
    );
    if (
      new Set(branchOrder).size !== branchOrder.length ||
      branchOrder.some(
        (branch, index) => index > 0 && branch <= branchOrder[index - 1],
      )
    ) {
      return fail(
        `${path}.version`,
        "unique Windows 11 branches from oldest to newest",
      );
    }
  }

  return { family, displayName, version, channel };
}

function readSource(value: unknown, path: string): ReportSource {
  const source = readObject(value, path);
  const type = readEnum(source.type, SOURCE_TYPES, `${path}.type`);
  const url = readString(source.url, `${path}.url`);
  const retrievedAt = readOptionalNullableDateTime(source, "retrievedAt", path);

  let parsedUrl: URL;
  try {
    parsedUrl = new URL(url);
  } catch {
    return fail(`${path}.url`, "a valid URL");
  }
  if (
    parsedUrl.protocol !== "https:" ||
    !SOURCE_HOSTS[type].includes(parsedUrl.hostname)
  ) {
    return fail(`${path}.url`, `an official HTTPS source for ${type}`);
  }

  return { type, url, retrievedAt };
}

function readUpdate(
  value: unknown,
  index: number,
  reportStatus: ReportStatus,
): UpdateRecord {
  const path = `updates[${index}]`;
  const update = readObject(value, path);
  const kb = readString(update.kb, `${path}.kb`);
  if (!KB_PATTERN.test(kb)) {
    return fail(`${path}.kb`, "KB<number> or NO PUBLICADO");
  }

  const os = readOs(update.os, `${path}.os`);
  const updateType = readEnum(
    update.updateType,
    UPDATE_TYPES,
    `${path}.updateType`,
  );
  const releaseDate =
    update.releaseDate === null
      ? null
      : readDate(update.releaseDate, `${path}.releaseDate`);
  const knownIssuesStatus = readEnum(
    update.knownIssuesStatus,
    KNOWN_ISSUES_STATUSES,
    `${path}.knownIssuesStatus`,
  );
  const supersededBy = readNullableString(
    update.supersededBy,
    `${path}.supersededBy`,
  );
  if (supersededBy !== null && !SUPERSEDENCE_PATTERN.test(supersededBy)) {
    return fail(`${path}.supersededBy`, "KB<number> or null");
  }

  if (kb === "NO PUBLICADO") {
    if (
      releaseDate !== null ||
      knownIssuesStatus !== "not-published" ||
      supersededBy !== null
    ) {
      return fail(path, "explicit not-published semantics for NO PUBLICADO");
    }
  } else if (knownIssuesStatus === "not-published") {
    return fail(`${path}.knownIssuesStatus`, "a published-update status");
  }

  if ((knownIssuesStatus === "oob") !== (supersededBy !== null)) {
    return fail(path, "matching oob status and supersededBy fields");
  }

  if (updateType === "esu" && os.channel !== "ESU") {
    return fail(`${path}.updateType`, "esu only for an ESU operating system");
  }

  const rawSources = update.sources;
  if (rawSources === undefined && reportStatus === "manual-golden-fixture") {
    // The single manual golden fixture predates source capture; normalize omission.
  } else if (!Array.isArray(rawSources)) {
    return fail(`${path}.sources`, "an array");
  }
  const sources = Array.isArray(rawSources) ? rawSources : [];
  if (reportStatus !== "manual-golden-fixture" && sources.length === 0) {
    return fail(`${path}.sources`, "a non-empty provenance array");
  }

  return {
    kb,
    os,
    updateType,
    releaseDate,
    changesSummary: readNonEmptyString(
      update.changesSummary,
      `${path}.changesSummary`,
    ),
    resolvedIssuesSummary: readNonEmptyString(
      update.resolvedIssuesSummary,
      `${path}.resolvedIssuesSummary`,
    ),
    knownIssuesSummary: readNonEmptyString(
      update.knownIssuesSummary,
      `${path}.knownIssuesSummary`,
    ),
    knownIssuesStatus,
    supersededBy,
    sources: sources.map((source, sourceIndex) =>
      readSource(source, `${path}.sources[${sourceIndex}]`),
    ),
  };
}

export function loadMonthlyReport(rawReport: unknown): MonthlyReport {
  const report = readObject(rawReport, "report");
  const schemaVersion = readString(report.schemaVersion, "schemaVersion");
  if (schemaVersion !== "1.0.0") {
    return fail("schemaVersion", "1.0.0");
  }

  const reportMonth = readString(report.reportMonth, "reportMonth");
  if (!REPORT_MONTH_PATTERN.test(reportMonth)) {
    return fail("reportMonth", "YYYY-MM");
  }

  const generatedAt = readOptionalNullableDateTime(
    report,
    "generatedAt",
    "report",
  );
  const patchTuesdayDate = readDate(
    report.patchTuesdayDate,
    "patchTuesdayDate",
  );
  const status = readEnum(report.status, REPORT_STATUSES, "status");
  if (
    status === "manual-golden-fixture" &&
    (reportMonth !== "2026-08" ||
      patchTuesdayDate !== "2026-08-11" ||
      generatedAt !== null)
  ) {
    return fail("report", "the declared August 2026 golden-fixture identity");
  }

  if (!Array.isArray(report.updates)) {
    return fail("updates", "an array");
  }

  return sortMonthlyReport({
    schemaVersion,
    reportMonth,
    patchTuesdayDate,
    generatedAt,
    status,
    updates: report.updates.map((update, index) =>
      readUpdate(update, index, status),
    ),
  });
}
