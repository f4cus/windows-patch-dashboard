import { loadAugustReport } from "./data/augustReport";
import type { MonthlyReport } from "./data/model";
import "./styles.css";

type ReportState =
  | { readonly status: "ready"; readonly report: MonthlyReport }
  | { readonly status: "error"; readonly message: string };

function createReportState(): ReportState {
  try {
    return { status: "ready", report: loadAugustReport() };
  } catch (error: unknown) {
    return {
      status: "error",
      message:
        error instanceof Error
          ? error.message
          : "The fixture could not be validated.",
    };
  }
}

const reportState = createReportState();

export default function App() {
  if (reportState.status === "error") {
    return (
      <main className="report-shell">
        <h1>Windows Patch Dashboard</h1>
        <p role="alert">
          No se pudo cargar el reporte de desarrollo: {reportState.message}
        </p>
      </main>
    );
  }

  const { report } = reportState;

  return (
    <main className="report-shell">
      <header>
        <h1>Windows Patch Dashboard</h1>
        <p>
          Mes del reporte: <strong>{report.reportMonth}</strong>
          {" · "}
          Actualizaciones: <strong>{report.updates.length}</strong>
        </p>
      </header>

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">KB</th>
              <th scope="col">OS</th>
              <th scope="col">Vulnerabilidades / Cambios Clave</th>
              <th scope="col">Issues Resueltos</th>
              <th scope="col">Problemas Conocidos</th>
            </tr>
          </thead>
          <tbody>
            {report.updates.map((update, index) => (
              <tr key={`${update.os.displayName}-${update.kb}-${index}`}>
                <td>{update.kb}</td>
                <td>{update.os.displayName}</td>
                <td>{update.changesSummary}</td>
                <td>{update.resolvedIssuesSummary}</td>
                <td>{update.knownIssuesSummary}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
