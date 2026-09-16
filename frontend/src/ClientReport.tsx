import type { MonthlyReport, UpdateRecord } from "./data/model";
import {
  formatDate,
  formatDateTime,
  formatReportMonth,
  KNOWN_ISSUES_LABELS,
  PARTIAL_REPORT_EXPLANATION,
  REPORT_STATUS_LABELS,
  SOURCE_LABELS,
  UPDATE_TYPE_LABELS,
} from "./reportPresentation";

interface ClientReportProps {
  readonly report: MonthlyReport;
  readonly updates: readonly UpdateRecord[];
  readonly scopeLabel: string;
}

function groupByOperatingSystem(updates: readonly UpdateRecord[]) {
  const groups = new Map<string, UpdateRecord[]>();
  for (const update of updates) {
    const name = update.os.displayName;
    const group = groups.get(name) ?? [];
    group.push(update);
    groups.set(name, group);
  }
  return groups;
}

function ClientUpdate({ update }: { readonly update: UpdateRecord }) {
  return (
    <section className="client-update" aria-label={update.kb}>
      <header className="client-update__header">
        <h3>{update.kb}</h3>
        <span className="client-update__type" data-type={update.updateType}>
          {UPDATE_TYPE_LABELS[update.updateType]}
        </span>
        <span className="client-update__date">
          Publicada: {formatDate(update.releaseDate)}
        </span>
      </header>

      <section className="client-update__detail">
        <h4>Cambios destacados</h4>
        <p>{update.changesSummary}</p>
      </section>
      <section className="client-update__detail">
        <h4>Correcciones</h4>
        <p>{update.resolvedIssuesSummary}</p>
      </section>
      <section className="client-update__detail">
        <h4>Problemas conocidos</h4>
        <p
          className="client-update__status"
          data-status={update.knownIssuesStatus}
        >
          {KNOWN_ISSUES_LABELS[update.knownIssuesStatus]}
        </p>
        {update.knownIssuesStatus === "none" ? null : (
          <p>{update.knownIssuesSummary}</p>
        )}
        {update.supersededBy === null ? null : (
          <p>Reemplazada por {update.supersededBy}</p>
        )}
      </section>
      <section className="client-update__detail client-update__sources">
        <h4>Fuentes oficiales</h4>
        {update.sources.length === 0 ? (
          <p>No disponibles.</p>
        ) : (
          <ul>
            {update.sources.map((source) => (
              <li key={`${source.type}-${source.url}`}>
                <a href={source.url}>{SOURCE_LABELS[source.type]}</a>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}

export function ClientReport({
  report,
  updates,
  scopeLabel,
}: ClientReportProps) {
  return (
    <article className="client-report" aria-labelledby="client-report-title">
      <header className="client-report__header">
        <h1 id="client-report-title">Microsoft Patch Tuesday</h1>
        <p className="client-report__month">
          {formatReportMonth(report.reportMonth)}
        </p>
        <dl className="client-report__metadata">
          <div>
            <dt>Patch Tuesday</dt>
            <dd>{formatDate(report.patchTuesdayDate)}</dd>
          </div>
          <div>
            <dt>Informe actualizado</dt>
            <dd>{formatDateTime(report.generatedAt)}</dd>
          </div>
          <div>
            <dt>Alcance</dt>
            <dd>{scopeLabel}</dd>
          </div>
          <div>
            <dt>Estado</dt>
            <dd>{REPORT_STATUS_LABELS[report.status]}</dd>
          </div>
        </dl>
        {report.status === "partial" ? (
          <p className="client-report__notice">{PARTIAL_REPORT_EXPLANATION}</p>
        ) : null}
      </header>

      {updates.length === 0 ? (
        <p className="client-report__empty">
          Seleccione al menos un sistema operativo para incluir registros.
        </p>
      ) : (
        [...groupByOperatingSystem(updates)].map(
          ([operatingSystem, records]) => (
            <section className="client-os" key={operatingSystem}>
              <h2>{operatingSystem}</h2>
              {records.map((update, index) => (
                <ClientUpdate
                  key={`${update.kb}-${update.releaseDate}-${index}`}
                  update={update}
                />
              ))}
            </section>
          ),
        )
      )}
    </article>
  );
}
