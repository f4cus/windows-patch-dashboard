import type {
  KnownIssuesStatus,
  ReportSource,
  ReportStatus,
  UpdateType,
} from "./data/model";

export const REPORT_COLUMN_LABELS = [
  "KB",
  "Sistema operativo",
  "Cambios destacados",
  "Correcciones",
  "Problemas conocidos",
] as const;

export const SOURCE_LABELS: Readonly<Record<ReportSource["type"], string>> = {
  "microsoft-support": "Microsoft Support",
  msrc: "MSRC",
  "release-health": "Windows Release Health",
};

export const KNOWN_ISSUES_LABELS: Readonly<Record<KnownIssuesStatus, string>> =
  {
    none: "Microsoft no reporta problemas conocidos.",
    open: "Abierto",
    resolved: "Resuelto",
    "not-published": "No publicado",
    unknown: "No verificado",
  };

export const REPORT_STATUS_LABELS: Readonly<Record<ReportStatus, string>> = {
  generated: "Informe generado",
  verified: "Informe verificado",
  partial: "Informe parcial",
  "manual-golden-fixture": "Informe de prueba",
};

export const PARTIAL_REPORT_EXPLANATION =
  "Parte de la información no pudo verificarse completamente en las fuentes oficiales.";

export const UPDATE_TYPE_LABELS: Readonly<Record<UpdateType, string>> = {
  security: "Seguridad",
  oob: "OOB",
  preview: "Preview",
  unknown: "Tipo desconocido",
};

const DATE_FORMATTER = new Intl.DateTimeFormat("es-AR", {
  day: "numeric",
  month: "long",
  timeZone: "UTC",
  year: "numeric",
});

const MONTH_FORMATTER = new Intl.DateTimeFormat("es-AR", {
  month: "long",
  timeZone: "UTC",
  year: "numeric",
});

const COMPACT_DATE_FORMATTER = new Intl.DateTimeFormat("es-AR", {
  day: "2-digit",
  month: "2-digit",
  timeZone: "UTC",
  year: "numeric",
});

function parseIsoDate(value: string): Date {
  return new Date(`${value}T00:00:00Z`);
}

export function formatReportMonth(reportMonth: string): string {
  return MONTH_FORMATTER.format(parseIsoDate(`${reportMonth}-01`));
}

export function formatDate(value: string | null): string {
  return value === null
    ? "No publicado"
    : DATE_FORMATTER.format(parseIsoDate(value));
}

export function formatCompactDate(value: string | null): string {
  return value === null
    ? "No publicado"
    : COMPACT_DATE_FORMATTER.format(parseIsoDate(value));
}

export function formatDateTime(value: string | null): string {
  return value === null
    ? "No disponible"
    : DATE_FORMATTER.format(new Date(value));
}
