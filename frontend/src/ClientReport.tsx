import type { MonthlyReport, UpdateRecord } from "./data/model";
import {
  formatCompactDate,
  formatDate,
  formatDateTime,
  formatReportMonth,
  KNOWN_ISSUES_LABELS,
  REPORT_STATUS_LABELS,
  SOURCE_LABELS,
  UPDATE_TYPE_LABELS,
  PUBLICATION_LABELS,
  recordLabel,
  recordDate,
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
    <section className="client-update" aria-label={recordLabel(update)}>
      <header className="client-update__header">
        <h3>{recordLabel(update)}</h3>
        {update.publicationStatus ? (
          <span>{PUBLICATION_LABELS[update.publicationStatus]}</span>
        ) : null}
        <span className="client-update__type" data-type={update.updateType}>
          {update.kb === "NO PUBLICADO" && update.publicationStatus
            ? "No aplica"
            : UPDATE_TYPE_LABELS[update.updateType]}
        </span>
        <span className="client-update__date">
          {update.releaseDate === null ? "Fecha" : "Publicada"}:{" "}
          {recordDate(update)}
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
          {update.kb === "NO PUBLICADO" && update.publicationStatus
            ? "No aplica: sin actualización"
            : KNOWN_ISSUES_LABELS[update.knownIssuesStatus]}
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
            {[...update.sources, ...(update.retainedSources ?? [])].map(
              (source) => (
                <li
                  key={`${source.type}-${source.url}-${source.retrievedAt ?? ""}`}
                >
                  <a href={source.url}>{SOURCE_LABELS[source.type]}</a>
                </li>
              ),
            )}
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
  const operatingSystemGroups = [...groupByOperatingSystem(updates)];
  const orderedUpdates = operatingSystemGroups.flatMap(
    ([, records]) => records,
  );
  const unknownKnownIssues = updates.filter(
    (update) =>
      update.kb !== "NO PUBLICADO" && update.knownIssuesStatus === "unknown",
  );
  const securityCount = updates.filter(
    (update) =>
      update.kb !== "NO PUBLICADO" && update.updateType === "security",
  ).length;
  const oobCount = updates.filter(
    (update) => update.updateType === "oob",
  ).length;

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
      </header>

      {updates.length > 0 ? (
        <section
          className="client-report__summary"
          aria-labelledby="client-summary-title"
        >
          <h2 id="client-summary-title">Resumen ejecutivo</h2>
          <p className="client-report__summary-metrics">
            {operatingSystemGroups.length}{" "}
            {operatingSystemGroups.length === 1
              ? "sistema operativo"
              : "sistemas operativos"}{" "}
            · {securityCount}{" "}
            {securityCount === 1
              ? "actualización de seguridad"
              : "actualizaciones de seguridad"}{" "}
            · {oobCount} OOB ·{" "}
            {unknownKnownIssues.length === 0
              ? "Sin estados no verificados"
              : `${unknownKnownIssues.length} ${unknownKnownIssues.length === 1 ? "estado no verificado" : "estados no verificados"}`}
          </p>
          <table className="client-report__summary-table">
            <colgroup>
              <col className="client-report__summary-os" />
              <col className="client-report__summary-kb" />
              <col className="client-report__summary-type" />
              <col className="client-report__summary-date" />
              <col className="client-report__summary-status" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">Sistema operativo</th>
                <th scope="col">KB</th>
                <th scope="col">Tipo</th>
                <th scope="col">Publicación</th>
                <th scope="col">Problemas conocidos</th>
              </tr>
            </thead>
            <tbody>
              {orderedUpdates.map((update, index) => (
                <tr key={`${update.os.displayName}-${update.kb}-${index}`}>
                  <td>{update.os.displayName}</td>
                  <td>{recordLabel(update)}</td>
                  <td>
                    {update.kb === "NO PUBLICADO" && update.publicationStatus
                      ? "No aplica"
                      : UPDATE_TYPE_LABELS[update.updateType]}
                  </td>
                  <td>
                    {update.lifecycle || update.publicationStatus === "pending"
                      ? recordDate(update)
                      : formatCompactDate(update.releaseDate)}
                  </td>
                  <td>
                    {update.kb === "NO PUBLICADO" && update.publicationStatus
                      ? "No aplica: sin actualización"
                      : update.knownIssuesStatus === "none"
                        ? "Sin problemas conocidos"
                        : KNOWN_ISSUES_LABELS[update.knownIssuesStatus]}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}

      {updates.length === 0 ? (
        <p className="client-report__empty">
          Seleccione al menos un sistema operativo para incluir registros.
        </p>
      ) : (
        <section
          className="client-report__detail"
          aria-labelledby="client-detail-title"
        >
          <h2 id="client-detail-title">Detalle por sistema operativo</h2>
          {operatingSystemGroups.map(([operatingSystem, records]) => (
            <section className="client-os" key={operatingSystem}>
              <h2>{operatingSystem}</h2>
              {records.map((update, index) => (
                <ClientUpdate
                  key={`${update.kb}-${update.releaseDate}-${index}`}
                  update={update}
                />
              ))}
            </section>
          ))}
        </section>
      )}

      {report.status === "partial" ? (
        <section
          className="client-report__verification"
          aria-labelledby="client-verification-title"
        >
          <h2 id="client-verification-title">Notas de verificación</h2>
          {report.schemaVersion === "1.1.0" ? (
            <>
              <p>
                El informe tiene campos o fuentes pendientes de verificación.
                Los campos no disponibles permanecen explícitos; la información
                confirmada anteriormente conserva sus fuentes y fechas
                originales.
              </p>
              <ul>
                {updates
                  .filter(
                    (update) =>
                      update.publicationStatus === "partial" ||
                      update.publicationStatus === "pending",
                  )
                  .map((update) => (
                    <li key={`${update.os.displayName}-${update.kb}`}>
                      {update.kb} — {update.os.displayName}:{" "}
                      {
                        PUBLICATION_LABELS[
                          update.publicationStatus as "partial" | "pending"
                        ]
                      }
                    </li>
                  ))}
              </ul>
            </>
          ) : unknownKnownIssues.length > 0 ? (
            <>
              <p>
                El informe está marcado como parcial. En los siguientes
                registros incluidos, la clasificación del estado de problemas
                conocidos figura como «No verificado». La información disponible
                se conserva sin inferir un estado:
              </p>
              <ul>
                {unknownKnownIssues.map((update, index) => (
                  <li key={`${update.os.displayName}-${update.kb}-${index}`}>
                    {update.kb} — {update.os.displayName}
                  </li>
                ))}
              </ul>
              <p>
                Esta limitación se refiere a la clasificación de problemas
                conocidos; los KB, sistemas operativos, fechas de publicación,
                tipos de actualización y fuentes oficiales se presentan según
                los registros del reporte.
              </p>
            </>
          ) : (
            <p>
              El informe está marcado como parcial. Los registros incluidos no
              muestran problemas conocidos con estado «No verificado»; los datos
              del reporte no detallan otra causa para esta selección.
            </p>
          )}
        </section>
      ) : null}
    </article>
  );
}
