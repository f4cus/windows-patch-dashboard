import { useEffect, useMemo, useRef, useState } from "react";
import type { MonthlyReport } from "./data/model";
import { localReports } from "./data/reportCatalog";
import { exportReportAsPng } from "./exportReport";
import { ReportSurface } from "./ReportSurface";
import { formatReportMonth } from "./reportPresentation";
import { useTheme } from "./useTheme";
import "./styles.css";

type ViewMode = "interactive" | "report";
type ExportState = "idle" | "exporting" | "error";

export type ReportExporter = (
  reportElement: HTMLElement,
  filenameBase: string,
) => Promise<void>;

interface AppProps {
  readonly reports?: readonly MonthlyReport[];
  readonly exporter?: ReportExporter;
}

const PROJECT_URL = "https://f4cus.github.io/windows-patch-dashboard/";
const REPOSITORY_URL = "https://github.com/f4cus/windows-patch-dashboard";
const LINKEDIN_URL = "https://www.linkedin.com/in/fvillagra/";

const LEGEND_ITEMS = [
  {
    status: "none",
    label: "Microsoft no reporta problemas conocidos.",
    symbol: "—",
  },
  { status: "open", label: "Abierto", symbol: "!" },
  { status: "resolved", label: "Resuelto", symbol: "✓" },
  { status: "not-published", label: "No publicado", symbol: "—" },
  { status: "unknown", label: "No verificado", symbol: "?" },
] as const;

function MoonIcon() {
  return (
    <svg
      aria-hidden="true"
      className="theme-toggle__icon"
      data-icon="moon"
      viewBox="0 0 24 24"
    >
      <path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5 8.5 8.5 0 1 0 20.5 14.2Z" />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg
      aria-hidden="true"
      className="theme-toggle__icon"
      data-icon="sun"
      viewBox="0 0 24 24"
    >
      <circle cx="12" cy="12" r="3.5" />
      <path d="M12 2v2.25M12 19.75V22M4.93 4.93l1.59 1.59M17.48 17.48l1.59 1.59M2 12h2.25M19.75 12H22M4.93 19.07l1.59-1.59M17.48 6.52l1.59-1.59" />
    </svg>
  );
}

export default function App({
  reports = localReports,
  exporter = exportReportAsPng,
}: AppProps) {
  const availableReports = useMemo(
    () =>
      [...reports].sort((left, right) =>
        right.reportMonth.localeCompare(left.reportMonth),
      ),
    [reports],
  );
  const [selectedMonth, setSelectedMonth] = useState(
    () => availableReports[0]?.reportMonth ?? "",
  );
  const [osSelections, setOsSelections] = useState<
    Readonly<Record<string, readonly string[]>>
  >({});
  const [mode, setMode] = useState<ViewMode>("interactive");
  const [exportState, setExportState] = useState<ExportState>("idle");
  const reportRef = useRef<HTMLElement>(null);
  const { theme, toggleTheme } = useTheme();

  const report = useMemo(
    () =>
      availableReports.find(
        (candidate) => candidate.reportMonth === selectedMonth,
      ),
    [availableReports, selectedMonth],
  );

  const availableOperatingSystems = useMemo(
    () =>
      report === undefined
        ? []
        : [...new Set(report.updates.map((update) => update.os.displayName))],
    [report],
  );

  const selectedOperatingSystems = useMemo(() => {
    const storedSelection = osSelections[selectedMonth];
    if (storedSelection === undefined) {
      return availableOperatingSystems;
    }

    const validSelection = availableOperatingSystems.filter((operatingSystem) =>
      storedSelection.includes(operatingSystem),
    );
    return storedSelection.length > 0 && validSelection.length === 0
      ? availableOperatingSystems
      : validSelection;
  }, [availableOperatingSystems, osSelections, selectedMonth]);
  const selectedOperatingSystemSet = useMemo(
    () => new Set(selectedOperatingSystems),
    [selectedOperatingSystems],
  );

  const updates = useMemo(
    () =>
      report?.updates.filter((update) =>
        selectedOperatingSystemSet.has(update.os.displayName),
      ) ?? [],
    [report, selectedOperatingSystemSet],
  );

  useEffect(() => {
    if (mode !== "report") {
      return undefined;
    }

    const exitReportMode = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMode("interactive");
      }
    };

    window.addEventListener("keydown", exitReportMode);
    return () => window.removeEventListener("keydown", exitReportMode);
  }, [mode]);

  if (report === undefined) {
    return (
      <main className="load-error">
        <h1>Windows Patch Dashboard</h1>
        <p role="alert">No hay informes disponibles.</p>
      </main>
    );
  }

  const currentReport = report;
  const allOperatingSystemsSelected =
    selectedOperatingSystems.length === availableOperatingSystems.length;
  const scopeLabel = allOperatingSystemsSelected
    ? "Todos los sistemas operativos"
    : selectedOperatingSystems.length === 1
      ? selectedOperatingSystems[0]
      : selectedOperatingSystems.length === 0
        ? "Sin sistemas seleccionados"
        : `${selectedOperatingSystems.length} de ${availableOperatingSystems.length} sistemas operativos`;

  function setOperatingSystems(operatingSystems: readonly string[]) {
    setOsSelections((currentSelections) => ({
      ...currentSelections,
      [selectedMonth]: operatingSystems,
    }));
  }

  function toggleOperatingSystem(operatingSystem: string) {
    setOperatingSystems(
      selectedOperatingSystemSet.has(operatingSystem)
        ? selectedOperatingSystems.filter(
            (selected) => selected !== operatingSystem,
          )
        : availableOperatingSystems.filter(
            (available) =>
              selectedOperatingSystemSet.has(available) ||
              available === operatingSystem,
          ),
    );
  }

  async function handleExport() {
    if (
      reportRef.current === null ||
      exportState === "exporting" ||
      updates.length === 0
    ) {
      return;
    }

    setExportState("exporting");
    try {
      await exporter(
        reportRef.current,
        `microsoft-patch-tuesday-${currentReport.reportMonth}`,
      );
      setExportState("idle");
    } catch {
      setExportState("error");
    }
  }

  if (mode === "report") {
    return (
      <main className="report-mode-shell">
        <p className="sr-only" role="status">
          Modo informe activo. Presione Escape para volver al modo interactivo.
        </p>
        <div className="report-mode-actions">
          <button
            className="button button--secondary"
            type="button"
            aria-label="Volver a vista interactiva"
            onClick={() => setMode("interactive")}
          >
            ← Volver
          </button>
        </div>
        <div className="report-viewport">
          <ReportSurface
            ref={reportRef}
            report={currentReport}
            updates={updates}
            scopeLabel={scopeLabel}
            interactive={false}
            theme={theme}
          />
        </div>
      </main>
    );
  }

  return (
    <div className="interactive-shell">
      <header className="app-nav" aria-label="Cabecera de la aplicación">
        <div className="wordmark">
          <span>Windows Patch Dashboard</span>
        </div>
        <div className="app-actions">
          <button
            className="theme-toggle"
            type="button"
            role="switch"
            aria-checked={theme === "dark"}
            aria-label={
              theme === "dark"
                ? "Cambiar a modo claro"
                : "Cambiar a modo oscuro"
            }
            title={
              theme === "dark"
                ? "Cambiar a modo claro"
                : "Cambiar a modo oscuro"
            }
            onClick={toggleTheme}
          >
            {theme === "dark" ? <SunIcon /> : <MoonIcon />}
          </button>
          <button
            className="button button--secondary"
            type="button"
            onClick={() => setMode("report")}
          >
            Modo informe
          </button>
        </div>
      </header>

      <main className="app-main">
        <section className="operator-bar" aria-label="Controles del informe">
          {availableReports.length > 1 ? (
            <div className="control-group">
              <label htmlFor="report-month">Mes del informe</label>
              <select
                id="report-month"
                value={selectedMonth}
                onChange={(event) => setSelectedMonth(event.target.value)}
              >
                {availableReports.map((candidate) => (
                  <option
                    key={candidate.reportMonth}
                    value={candidate.reportMonth}
                  >
                    {formatReportMonth(candidate.reportMonth)}
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          <details className="os-filter">
            <summary
              aria-label={`Sistemas operativos: ${selectedOperatingSystems.length} de ${availableOperatingSystems.length} seleccionados`}
            >
              <span>Sistemas operativos</span>
              <strong>
                {selectedOperatingSystems.length}/
                {availableOperatingSystems.length}
              </strong>
            </summary>
            <div className="os-filter__panel">
              <div className="os-filter__actions">
                <button
                  type="button"
                  disabled={allOperatingSystemsSelected}
                  onClick={() => setOperatingSystems(availableOperatingSystems)}
                >
                  Seleccionar todos
                </button>
                <button
                  type="button"
                  disabled={selectedOperatingSystems.length === 0}
                  onClick={() => setOperatingSystems([])}
                >
                  Limpiar
                </button>
              </div>
              <fieldset>
                <legend className="sr-only">
                  Seleccionar sistemas operativos
                </legend>
                {availableOperatingSystems.map((operatingSystem) => (
                  <label key={operatingSystem}>
                    <input
                      type="checkbox"
                      checked={selectedOperatingSystemSet.has(operatingSystem)}
                      onChange={() => toggleOperatingSystem(operatingSystem)}
                    />
                    <span>{operatingSystem}</span>
                  </label>
                ))}
              </fieldset>
            </div>
          </details>

          <div className="export-action">
            <button
              className="button button--secondary"
              type="button"
              disabled={exportState === "exporting" || updates.length === 0}
              aria-disabled={
                exportState === "exporting" || updates.length === 0
              }
              onClick={() => void handleExport()}
            >
              {exportState === "exporting" ? "Preparando PNG…" : "Exportar PNG"}
            </button>
            <span className="export-message" aria-live="polite">
              {exportState === "error"
                ? "No se pudo generar el PNG. Intente nuevamente."
                : updates.length === 0
                  ? "Seleccione al menos un sistema operativo."
                  : null}
            </span>
          </div>
        </section>

        <details className="status-legend">
          <summary>Referencia de estados</summary>
          <ul>
            {LEGEND_ITEMS.map((item) => (
              <li key={item.status} data-status={item.status}>
                <span aria-hidden="true">{item.symbol}</span>
                {item.label}
              </li>
            ))}
          </ul>
        </details>

        <div className="report-viewport">
          <ReportSurface
            ref={reportRef}
            report={currentReport}
            updates={updates}
            scopeLabel={scopeLabel}
            interactive={true}
            theme={theme}
          />
        </div>
      </main>
      <footer className="app-footer">
        <a href={PROJECT_URL}>Windows Patch Dashboard</a>
        <span>Facu Villagra</span>
        <span aria-hidden="true">·</span>
        <a href={LINKEDIN_URL} target="_blank" rel="noreferrer">
          LinkedIn
        </a>
        <span aria-hidden="true">·</span>
        <a href={REPOSITORY_URL} target="_blank" rel="noreferrer">
          GitHub
        </a>
      </footer>
    </div>
  );
}
