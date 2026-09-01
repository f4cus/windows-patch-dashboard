import { forwardRef, useId, useState } from "react";
import type {
  KnownIssuesStatus,
  MonthlyReport,
  ReportStatus,
  ReportSource,
  UpdateRecord,
  UpdateType,
} from "./data/model";
import {
  formatDate,
  formatDateTime,
  formatReportMonth,
  REPORT_COLUMN_LABELS,
  SOURCE_LABELS,
} from "./reportPresentation";
import type { ColorTheme } from "./useTheme";

const STATUS_PRESENTATION: Readonly<
  Record<KnownIssuesStatus, { readonly label: string; readonly symbol: string }>
> = {
  none: {
    label: "Microsoft no reporta problemas conocidos.",
    symbol: "—",
  },
  open: { label: "Abierto", symbol: "!" },
  resolved: { label: "Resuelto", symbol: "✓" },
  "not-published": { label: "No publicado", symbol: "—" },
  unknown: { label: "No verificado", symbol: "?" },
};

const REPORT_STATUS_LABELS: Readonly<Record<ReportStatus, string>> = {
  generated: "Informe generado",
  verified: "Informe verificado",
  partial: "Informe parcial",
  "manual-golden-fixture": "Informe de prueba",
};

const PARTIAL_REPORT_EXPLANATION =
  "Parte de la información no pudo verificarse completamente en las fuentes oficiales.";

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

const PREVIEW_CHARACTER_LIMIT = 180;

function createTextPreview(text: string): string {
  const value = text.trim();
  const characters = Array.from(value);
  if (characters.length <= PREVIEW_CHARACTER_LIMIT) {
    return value;
  }

  const candidate = characters.slice(0, PREVIEW_CHARACTER_LIMIT).join("");
  const wordBoundary = candidate.lastIndexOf(" ");
  const end =
    wordBoundary > PREVIEW_CHARACTER_LIMIT / 2
      ? wordBoundary
      : candidate.length;
  return `${candidate.slice(0, end).trimEnd()}…`;
}

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

function SourceList({
  id,
  expanded,
  sources,
}: {
  readonly id: string;
  readonly expanded: boolean;
  readonly sources: readonly ReportSource[];
}) {
  return (
    <div
      className="record-sources report-interactive"
      id={id}
      aria-hidden={!expanded}
    >
      <h3>{`Fuentes oficiales (${sources.length})`}</h3>
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
    </div>
  );
}

function RecordCopy({
  detailId,
  expanded,
  interactive,
  text,
}: {
  readonly detailId: string;
  readonly expanded: boolean;
  readonly interactive: boolean;
  readonly text: string;
}) {
  if (!interactive) {
    return <p className="record-copy record-copy--full">{text}</p>;
  }

  return (
    <>
      <p className="record-copy record-copy--preview" aria-hidden={expanded}>
        {createTextPreview(text)}
      </p>
      <p
        className="record-copy record-copy--full"
        id={detailId}
        aria-hidden={!expanded}
      >
        {text}
      </p>
    </>
  );
}

function getMicrosoftSupportUrl(
  sources: readonly ReportSource[],
): string | null {
  for (const source of sources) {
    if (source.type !== "microsoft-support") {
      continue;
    }

    try {
      const url = new URL(source.url);
      if (
        url.protocol === "https:" &&
        url.hostname === "support.microsoft.com"
      ) {
        return url.href;
      }
    } catch {
      // Ignore malformed source URLs and preserve the KB text fallback.
    }
  }

  return null;
}

function ReportRow({
  update,
  interactive,
}: {
  readonly update: UpdateRecord;
  readonly interactive: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const detailId = useId();
  const changesId = `${detailId}-changes`;
  const resolvedId = `${detailId}-resolved`;
  const knownIssuesId = `${detailId}-known-issues`;
  const sourcesId = `${detailId}-sources`;
  const supportUrl = interactive
    ? getMicrosoftSupportUrl(update.sources)
    : null;
  const kbClassName =
    update.kb === "NO PUBLICADO" ? "kb-unpublished" : "kb-number";
  const controlledIds = [changesId, resolvedId];
  if (update.knownIssuesStatus !== "none") {
    controlledIds.push(knownIssuesId);
  }
  if (update.sources.length > 0) {
    controlledIds.push(sourcesId);
  }

  return (
    <tr data-expanded={interactive ? expanded : undefined}>
      <td className="kb-cell" data-label={REPORT_COLUMN_LABELS[0]}>
        <strong className={kbClassName}>
          {supportUrl === null || update.kb === "NO PUBLICADO" ? (
            update.kb
          ) : (
            <a
              className="kb-link"
              href={supportUrl}
              target="_blank"
              rel="noreferrer"
              aria-label={`Abrir ${update.kb} en Microsoft Support`}
            >
              {update.kb}
            </a>
          )}
        </strong>
        <span className="record-meta">
          {UPDATE_TYPE_LABELS[update.updateType]} ·{" "}
          {formatDate(update.releaseDate)}
        </span>
        {interactive ? (
          <button
            className="record-disclosure report-interactive"
            type="button"
            aria-controls={controlledIds.join(" ")}
            aria-expanded={expanded}
            aria-label={`${expanded ? "Ocultar detalle" : "Ver detalle completo"} de ${update.kb}`}
            onClick={() => setExpanded((current) => !current)}
          >
            {expanded ? "Ocultar detalle" : "Ver detalle completo"}
          </button>
        ) : null}
        {interactive && update.sources.length > 0 ? (
          <SourceList
            id={sourcesId}
            expanded={expanded}
            sources={update.sources}
          />
        ) : null}
      </td>
      <td className="os-cell" data-label={REPORT_COLUMN_LABELS[1]}>
        <strong>{update.os.displayName}</strong>
        {update.os.channel === null ? null : (
          <span className="channel-label">Canal {update.os.channel}</span>
        )}
      </td>
      <td data-label={REPORT_COLUMN_LABELS[2]}>
        <RecordCopy
          detailId={changesId}
          expanded={expanded}
          interactive={interactive}
          text={update.changesSummary}
        />
      </td>
      <td data-label={REPORT_COLUMN_LABELS[3]}>
        <RecordCopy
          detailId={resolvedId}
          expanded={expanded}
          interactive={interactive}
          text={update.resolvedIssuesSummary}
        />
      </td>
      <td className="known-issues-cell" data-label={REPORT_COLUMN_LABELS[4]}>
        <div className="known-issues-signals">
          <StatusLabel status={update.knownIssuesStatus} />
          {update.supersededBy === null ? null : (
            <span className="superseded-label">
              OOB · reemplazada por {update.supersededBy}
            </span>
          )}
        </div>
        {update.knownIssuesStatus === "none" ? null : (
          <RecordCopy
            detailId={knownIssuesId}
            expanded={expanded}
            interactive={interactive}
            text={update.knownIssuesSummary}
          />
        )}
      </td>
    </tr>
  );
}

interface ReportSurfaceProps {
  readonly report: MonthlyReport;
  readonly updates: readonly UpdateRecord[];
  readonly scopeLabel: string;
  readonly interactive: boolean;
  readonly theme: ColorTheme;
}

export const ReportSurface = forwardRef<HTMLElement, ReportSurfaceProps>(
  function ReportSurface(
    { report, updates, scopeLabel, interactive, theme },
    reportRef,
  ) {
    return (
      <article
        className="report-document"
        id="report"
        ref={reportRef}
        aria-labelledby="report-title"
        data-theme={theme}
        data-layout={interactive ? "interactive" : "report"}
      >
        <header className="report-header">
          <div className="report-title-block">
            <h1 id="report-title">Microsoft Patch Tuesday</h1>
            <p className="report-subtitle">
              <span>
                Informe mensual · {formatReportMonth(report.reportMonth)}
              </span>
              <span className="report-status" data-status={report.status}>
                {REPORT_STATUS_LABELS[report.status]}
              </span>
              {report.status === "partial" ? (
                <span className="report-status-explanation">
                  {PARTIAL_REPORT_EXPLANATION}
                </span>
              ) : null}
            </p>
          </div>
          <dl className="report-metadata">
            <div>
              <dt>Patch Tuesday</dt>
              <dd>{formatDate(report.patchTuesdayDate)}</dd>
            </div>
            <div>
              <dt>Datos actualizados</dt>
              <dd>{formatDateTime(report.generatedAt)}</dd>
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
          <span className="report-footer__project">
            Windows Patch Dashboard · f4cus.github.io/windows-patch-dashboard
          </span>
          <span>
            Desarrollado por Facu Villagra · linkedin.com/in/fvillagra
          </span>
        </footer>
      </article>
    );
  },
);
