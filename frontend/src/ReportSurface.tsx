import { forwardRef } from "react";
import type {
  KnownIssuesStatus,
  MonthlyReport,
  ReportSource,
  UpdateRecord,
  UpdateType,
} from "./data/model";
import {
  formatDate,
  formatDateTime,
  formatRenderedDate,
  formatReportMonth,
  REPORT_COLUMN_LABELS,
  SOURCE_LABELS,
} from "./reportPresentation";
import type { ColorTheme } from "./useTheme";

const STATUS_PRESENTATION: Readonly<
  Record<KnownIssuesStatus, { readonly label: string; readonly symbol: string }>
> = {
  none: { label: "Sin problemas conocidos", symbol: "—" },
  open: { label: "Abierto", symbol: "!" },
  resolved: { label: "Resuelto", symbol: "✓" },
  "not-published": { label: "No publicado", symbol: "—" },
  unknown: { label: "Desconocido", symbol: "?" },
};

const UPDATE_TYPE_LABELS: Readonly<Record<UpdateType, string>> = {
  security: "Seguridad",
  oob: "OOB",
  preview: "Preview",
  unknown: "Tipo desconocido",
};

const SOURCE_LINK_LABELS: Readonly<Record<ReportSource["type"], string>> = {
  "microsoft-support": "Support ↗",
  msrc: "MSRC ↗",
  "release-health": "Release Health ↗",
};

function StatusLabel({ status }: { readonly status: KnownIssuesStatus }) {
  const presentation = STATUS_PRESENTATION[status];

  return (
    <span className="status-label" data-status={status}>
      <span className="status-label__symbol" aria-hidden="true">
        {presentation.symbol}
      </span>
      {presentation.label}
    </span>
  );
}

function SourceDetails({
  sources,
}: {
  readonly sources: readonly ReportSource[];
}) {
  return (
    <details className="source-details report-interactive">
      <summary>{`Fuentes (${sources.length})`}</summary>
      <ul>
        {sources.map((source) => (
          <li key={`${source.type}-${source.url}`}>
            <a
              href={source.url}
              target="_blank"
              rel="noreferrer"
              aria-label={`Abrir ${SOURCE_LABELS[source.type]}`}
            >
              {SOURCE_LINK_LABELS[source.type]}
            </a>
            {source.retrievedAt === undefined ||
            source.retrievedAt === null ? null : (
              <span>Recuperada: {formatDateTime(source.retrievedAt)}</span>
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}

function ReportRow({
  update,
  interactive,
}: {
  readonly update: UpdateRecord;
  readonly interactive: boolean;
}) {
  return (
    <tr>
      <td className="kb-cell">
        <strong
          className={
            update.kb === "NO PUBLICADO" ? "kb-unpublished" : "kb-number"
          }
        >
          {update.kb}
        </strong>
        <span className="record-meta">
          {UPDATE_TYPE_LABELS[update.updateType]} ·{" "}
          {formatDate(update.releaseDate)}
        </span>
        {interactive && update.sources.length > 0 ? (
          <SourceDetails sources={update.sources} />
        ) : null}
      </td>
      <td className="os-cell">
        <strong>{update.os.displayName}</strong>
        {update.os.channel === null ? null : (
          <span className="channel-label">Canal {update.os.channel}</span>
        )}
      </td>
      <td>{update.changesSummary}</td>
      <td>{update.resolvedIssuesSummary}</td>
      <td className="known-issues-cell">
        <div className="known-issues-signals">
          <StatusLabel status={update.knownIssuesStatus} />
          {update.supersededBy === null ? null : (
            <span className="superseded-label">
              OOB · reemplazada por {update.supersededBy}
            </span>
          )}
        </div>
        <p>{update.knownIssuesSummary}</p>
      </td>
    </tr>
  );
}

interface ReportSurfaceProps {
  readonly report: MonthlyReport;
  readonly updates: readonly UpdateRecord[];
  readonly scopeLabel: string;
  readonly interactive: boolean;
  readonly renderedAt: Date;
  readonly theme: ColorTheme;
}

export const ReportSurface = forwardRef<HTMLElement, ReportSurfaceProps>(
  function ReportSurface(
    { report, updates, scopeLabel, interactive, renderedAt, theme },
    reportRef,
  ) {
    return (
      <article
        className="report-document"
        id="report"
        ref={reportRef}
        aria-labelledby="report-title"
        data-theme={theme}
      >
        <header className="report-header">
          <div className="report-title-block">
            <h1 id="report-title">Microsoft Patch Tuesday</h1>
            <p>Informe mensual · {formatReportMonth(report.reportMonth)}</p>
          </div>
          <dl className="report-metadata">
            <div>
              <dt>Patch Tuesday</dt>
              <dd>{formatDate(report.patchTuesdayDate)}</dd>
            </div>
            <div>
              <dt>Generado</dt>
              <dd>{formatRenderedDate(renderedAt)}</dd>
            </div>
            <div>
              <dt>Alcance</dt>
              <dd>{scopeLabel}</dd>
            </div>
            <div>
              <dt>Registros</dt>
              <dd>{updates.length}</dd>
            </div>
          </dl>
        </header>

        <div className="report-table-scroll">
          <table className="report-table">
            <colgroup>
              <col className="column-kb" />
              <col className="column-os" />
              <col className="column-changes" />
              <col className="column-resolved" />
              <col className="column-known" />
            </colgroup>
            <thead>
              <tr>
                {REPORT_COLUMN_LABELS.map((label) => (
                  <th scope="col" key={label}>
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {updates.map((update, index) => (
                <ReportRow
                  key={`${update.os.displayName}-${update.kb}-${index}`}
                  update={update}
                  interactive={interactive}
                />
              ))}
            </tbody>
          </table>
        </div>

        <footer className="report-footer">
          <span>
            Windows Patch Dashboard · {formatReportMonth(report.reportMonth)}
          </span>
        </footer>
      </article>
    );
  },
);
