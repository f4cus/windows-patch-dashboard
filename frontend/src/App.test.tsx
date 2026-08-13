// @vitest-environment jsdom

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import augustFixture from "../../data/fixtures/2026-08.json";
import App from "./App";
import { loadMonthlyReport } from "./data/loadMonthlyReport";
import type { MonthlyReport, UpdateRecord } from "./data/model";
import { THEME_STORAGE_KEY } from "./useTheme";

const augustReport = loadMonthlyReport(augustFixture);
const renderedAt = new Date("2026-08-13T12:00:00Z");

function installMatchMedia(prefersDark = false) {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: prefersDark,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
    writable: true,
  });
}

function renderApp(
  properties: Omit<React.ComponentProps<typeof App>, "renderedAt"> = {},
) {
  return render(
    <App reports={[augustReport]} renderedAt={renderedAt} {...properties} />,
  );
}

function updateWith(
  overrides: Partial<UpdateRecord>,
  base: UpdateRecord = augustReport.updates[0],
): UpdateRecord {
  return { ...base, ...overrides };
}

function reportWith(
  overrides: Partial<MonthlyReport>,
  updates: readonly UpdateRecord[] = augustReport.updates,
): MonthlyReport {
  return { ...augustReport, ...overrides, updates };
}

beforeEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  document.documentElement.style.colorScheme = "";
  installMatchMedia();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("V1 report experience", () => {
  it("renders all nine August records under exactly five canonical columns", () => {
    const { container } = renderApp();

    expect(container.querySelectorAll("thead th")).toHaveLength(5);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(9);
    expect(
      [...container.querySelectorAll("thead th")].map(
        (cell) => cell.textContent,
      ),
    ).toEqual([
      "KB",
      "OS",
      "Vulnerabilidades / Cambios Clave",
      "Issues Resueltos",
      "Problemas Conocidos",
    ]);
  });

  it("follows the system color preference initially", () => {
    installMatchMedia(true);

    renderApp();

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(
      screen
        .getByRole("switch", { name: "Cambiar a tema claro" })
        .getAttribute("aria-checked"),
    ).toBe("true");
  });

  it("toggles and persists an explicit theme preference", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
    renderApp();

    const toggle = screen.getByRole("switch", {
      name: "Cambiar a tema claro",
    });
    expect(document.documentElement.dataset.theme).toBe("dark");

    fireEvent.click(toggle);

    expect(document.documentElement.dataset.theme).toBe("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(
      screen
        .getByRole("switch", { name: "Cambiar a tema oscuro" })
        .getAttribute("aria-checked"),
    ).toBe("false");
  });

  it("selects individual operating systems in canonical report order", () => {
    const { container } = renderApp();
    const filter = screen.getByLabelText(
      "Sistemas operativos: 9 de 9 seleccionados",
    );

    expect(screen.getAllByRole("checkbox")).toHaveLength(9);
    expect(
      screen
        .getAllByRole<HTMLInputElement>("checkbox")
        .every((box) => box.checked),
    ).toBe(true);

    fireEvent.click(filter);
    fireEvent.click(
      screen.getByRole("checkbox", { name: "Windows Server 2022" }),
    );

    expect(container.querySelectorAll("tbody tr")).toHaveLength(8);
    expect(screen.queryByText("KB5120242")).toBeNull();
    expect(
      screen.getByLabelText("Sistemas operativos: 8 de 9 seleccionados"),
    ).toBeTruthy();
    expect(
      within(container.querySelector(".report-metadata")!).getByText("8"),
    ).toBeTruthy();
  });

  it("clears and selects all operating systems", () => {
    const { container } = renderApp();

    fireEvent.click(screen.getByRole("button", { name: "Limpiar" }));

    expect(
      screen
        .getAllByRole<HTMLInputElement>("checkbox")
        .every((box) => !box.checked),
    ).toBe(true);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(0);
    expect(
      screen.getByRole<HTMLButtonElement>("button", { name: "Exportar PNG" })
        .disabled,
    ).toBe(true);
    expect(
      screen.getByLabelText("Sistemas operativos: 0 de 9 seleccionados"),
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Seleccionar todos" }));

    expect(
      screen
        .getAllByRole<HTMLInputElement>("checkbox")
        .every((box) => box.checked),
    ).toBe(true);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(9);
  });

  it("carries the selected OS and filtered count into Report Mode", () => {
    const { container } = renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Limpiar" }));
    fireEvent.click(
      screen.getByRole("checkbox", { name: "Windows Server 2022" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Modo informe" }));

    expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
    expect(screen.getByText("KB5120242")).toBeTruthy();
    expect(
      within(container.querySelector("tbody")!).getByText(
        "Windows Server 2022",
      ),
    ).toBeTruthy();
    const metadata = within(container.querySelector(".report-metadata")!);
    expect(metadata.getByText("Windows Server 2022")).toBeTruthy();
    expect(metadata.getByText("1")).toBeTruthy();
    expect(container.querySelectorAll("thead th")).toHaveLength(5);
    expect(screen.queryByText("Sistemas operativos")).toBeNull();
    expect(screen.queryByRole("switch")).toBeNull();
  });

  it("renders only the public report metadata and current render date", () => {
    const { container } = renderApp();
    const metadata = container.querySelector<HTMLElement>(".report-metadata")!;

    expect(metadata.querySelectorAll(":scope > div")).toHaveLength(4);
    expect(
      [...metadata.querySelectorAll("dt")].map((item) => item.textContent),
    ).toEqual(["Patch Tuesday", "Generado", "Alcance", "Registros"]);
    expect(within(metadata).getByText("13 de agosto de 2026")).toBeTruthy();
    expect(container.textContent).not.toMatch(/fixture|proveniencia/i);
    expect(container.textContent).not.toContain("Sin fecha");
  });

  it("renders NO PUBLICADO explicitly", () => {
    const unpublished = updateWith({
      kb: "NO PUBLICADO",
      releaseDate: null,
      knownIssuesStatus: "not-published",
      supersededBy: null,
    });

    renderApp({ reports: [reportWith({}, [unpublished])] });

    expect(screen.getByText("NO PUBLICADO")).toBeTruthy();
    expect(
      screen.getByText("No publicado", { selector: ".status-label" }),
    ).toBeTruthy();
  });

  it("keeps known-issue status and OOB supersedence independent", () => {
    const openAndSuperseded = updateWith({
      knownIssuesStatus: "open",
      supersededBy: "KB5999999",
    });

    renderApp({ reports: [reportWith({}, [openAndSuperseded])] });

    expect(
      screen.getByText("Abierto", { selector: ".status-label" }),
    ).toBeTruthy();
    expect(screen.getByText("OOB · reemplazada por KB5999999")).toBeTruthy();
  });

  it("shows official source links in Interactive Mode", () => {
    const sourcedUpdate = updateWith({
      sources: [
        {
          type: "microsoft-support",
          url: "https://support.microsoft.com/help/5120386",
          retrievedAt: "2026-08-12T10:00:00Z",
        },
      ],
    });

    renderApp({ reports: [reportWith({}, [sourcedUpdate])] });
    fireEvent.click(screen.getByText("Fuentes (1)"));

    const link = screen.getByRole("link", { name: "Abrir Microsoft Support" });
    expect(link.getAttribute("href")).toBe(
      "https://support.microsoft.com/help/5120386",
    );
  });

  it("hides Interactive Mode controls and sources in Report Mode", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
    const { container } = renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Modo informe" }));

    expect(screen.queryByLabelText("Mes del informe")).toBeNull();
    expect(screen.queryByRole("button", { name: "Exportar PNG" })).toBeNull();
    expect(container.querySelector(".app-nav")).toBeNull();
    expect(container.querySelector(".source-details")).toBeNull();
    expect(container.querySelectorAll("thead th")).toHaveLength(5);
    expect(container.querySelector("#report")?.getAttribute("data-theme")).toBe(
      "dark",
    );
  });

  it("switches between locally available report months", () => {
    const julyReport = reportWith(
      {
        reportMonth: "2026-07",
        patchTuesdayDate: "2026-07-14",
        generatedAt: "2026-07-15T09:00:00Z",
        status: "verified",
      },
      [
        updateWith({
          kb: "KB5000001",
          sources: [
            {
              type: "msrc",
              url: "https://msrc.microsoft.com/update-guide",
              retrievedAt: "2026-07-15T08:00:00Z",
            },
          ],
        }),
      ],
    );

    const { container } = renderApp({
      reports: [augustReport, julyReport],
    });
    fireEvent.change(screen.getByLabelText("Mes del informe"), {
      target: { value: "2026-07" },
    });

    expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
    expect(screen.getByText("KB5000001")).toBeTruthy();
    expect(
      screen.getByLabelText("Sistemas operativos: 1 de 1 seleccionados"),
    ).toBeTruthy();
  });

  it("exports the filtered report surface in the active theme", async () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
    const exporter = vi.fn().mockResolvedValue(undefined);
    const { container } = renderApp({ exporter });

    fireEvent.click(screen.getByRole("button", { name: "Limpiar" }));
    fireEvent.click(
      screen.getByRole("checkbox", { name: "Windows Server 2022" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Exportar PNG" }));

    await waitFor(() => expect(exporter).toHaveBeenCalledTimes(1));
    const exportedReport = exporter.mock.calls[0][0] as HTMLElement;
    expect(exportedReport).toBe(container.querySelector("#report"));
    expect(exportedReport.dataset.theme).toBe("dark");
    expect(exportedReport.querySelectorAll("tbody tr")).toHaveLength(1);
    expect(exportedReport.textContent).toContain("KB5120242");
    expect(exporter).toHaveBeenCalledWith(
      exportedReport,
      "microsoft-patch-tuesday-2026-08",
    );
  });
});
