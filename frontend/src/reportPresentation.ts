import type { ReportSource } from "./data/model";

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

export function formatDateTime(value: string | null): string {
  return value === null
    ? "No disponible"
    : DATE_FORMATTER.format(new Date(value));
}
