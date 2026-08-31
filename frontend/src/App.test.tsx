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

function renderApp(properties: React.ComponentProps<typeof App> = {}) {
  return render(<App reports={[augustReport]} {...properties} />);
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
  it("removes the secondary editorial tagline", () => {
    renderApp();

    expect(
      within(screen.getByLabelText("Cabecera de la aplicación")).getByText(
        "Windows Patch Dashboard",
      ),
    ).toBeTruthy();
    expect(screen.queryByText(/lectura editorial/i)).toBeNull();
  });

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
        .getByRole("switch", { name: "Cambiar a modo claro" })
        .getAttribute("aria-checked"),
    ).toBe("true");
    expect(
      screen
        .getByRole("switch", { name: "Cambiar a modo claro" })
        .querySelector('[data-icon="sun"]'),
    ).toBeTruthy();
  });

  it("uses an accessible icon-only toggle and persists the theme", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
    renderApp();

    const toggle = screen.getByRole("switch", {
      name: "Cambiar a modo claro",
    });
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(toggle.textContent).toBe("");
    expect(toggle.querySelector('[data-icon="sun"]')).toBeTruthy();
    expect(screen.queryByText("Claro")).toBeNull();
    expect(screen.queryByText("Oscuro")).toBeNull();

    fireEvent.click(toggle);

    expect(document.documentElement.dataset.theme).toBe("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(
      screen
        .getByRole("switch", { name: "Cambiar a modo oscuro" })
        .getAttribute("aria-checked"),
    ).toBe("false");
    expect(
      screen
        .getByRole("switch", { name: "Cambiar a modo oscuro" })
        .querySelector('[data-icon="moon"]'),
    ).toBeTruthy();
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

  it("renders only public report metadata using the stable JSON timestamp", () => {
    const report = reportWith({
      generatedAt: "2026-08-29T02:49:12.152626Z",
    });
    const { container } = renderApp({ reports: [report] });
    const metadata = container.querySelector<HTMLElement>(".report-metadata")!;

    expect(metadata.querySelectorAll(":scope > div")).toHaveLength(4);
    expect(
      [...metadata.querySelectorAll("dt")].map((item) => item.textContent),
    ).toEqual(["Patch Tuesday", "Datos actualizados", "Alcance", "Registros"]);
    expect(within(metadata).getByText("29 de agosto de 2026")).toBeTruthy();
    expect(container.textContent).not.toMatch(/fixture|proveniencia/i);
    expect(container.textContent).not.toContain("Sin fecha");
  });

  it("renders a null generatedAt fixture as unavailable", () => {
    const { container } = renderApp();
    const metadata = within(
      container.querySelector<HTMLElement>(".report-metadata")!,
    );

    expect(metadata.getByText("Datos actualizados")).toBeTruthy();
    expect(metadata.getByText("No disponible")).toBeTruthy();
  });

  it.each([
    ["generated", "Informe generado"],
    ["verified", "Informe verificado"],
    ["partial", "Informe parcial"],
    ["manual-golden-fixture", "Informe de prueba"],
  ] as const)("maps report status %s to %s", (status, expectedLabel) => {
    const { container } = renderApp({
      reports: [reportWith({ status })],
    });

    expect(
      within(
        container.querySelector<HTMLElement>(".report-subtitle")!,
      ).getByText(expectedLabel),
    ).toBeTruthy();
  });

  it("explains a partial report safely beside the subtitle", () => {
    const { container } = renderApp({
      reports: [reportWith({ status: "partial" })],
    });
    const subtitle = container.querySelector<HTMLElement>(".report-subtitle")!;

    expect(within(subtitle).getByText("Informe parcial")).toBeTruthy();
    expect(
      within(subtitle).getByText(
        "Parte de la información no pudo verificarse completamente en las fuentes oficiales.",
      ),
    ).toBeTruthy();
    expect(
      container.querySelector(".report-metadata")?.textContent,
    ).not.toContain("Informe parcial");
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

  it("derives the canonical none copy and omits redundant source wording", () => {
    const sourceWording =
      "Microsoft no está al tanto de ningún problema con respecto a esta actualización.";
    const noneUpdate = updateWith({
      knownIssuesStatus: "none",
      knownIssuesSummary: sourceWording,
    });
    const { container } = renderApp({
      reports: [reportWith({}, [noneUpdate])],
    });
    const row = container.querySelector<HTMLElement>("tbody tr")!;

    expect(
      within(row).getByText("Microsoft no reporta problemas conocidos.", {
        selector: ".status-label",
      }),
    ).toBeTruthy();
    expect(within(row).queryByText(sourceWording)).toBeNull();
    expect(row.querySelector(".known-issues-cell p")).toBeNull();
    expect(
      within(container.querySelector<HTMLElement>(".status-legend")!).getByText(
        "Microsoft no reporta problemas conocidos.",
      ),
    ).toBeTruthy();
  });

  it("presents unknown evidence as not verified in the row and legend", () => {
    const unknownUpdate = updateWith({
      knownIssuesStatus: "unknown",
      knownIssuesSummary: "La evidencia disponible es ambigua.",
    });
    const { container } = renderApp({
      reports: [reportWith({}, [unknownUpdate])],
    });

    expect(
      within(container.querySelector<HTMLElement>("tbody")!).getByText(
        "No verificado",
      ),
    ).toBeTruthy();
    expect(
      within(container.querySelector<HTMLElement>(".status-legend")!).getByText(
        "No verificado",
      ),
    ).toBeTruthy();
    expect(screen.queryByText("Desconocido")).toBeNull();
  });

  it("links the KB directly to Microsoft Support in Interactive Mode", () => {
    const sourcedUpdate = updateWith({
      kb: "KB5120386",
      sources: [
        {
          type: "microsoft-support",
          url: "https://support.microsoft.com/help/5120386",
          retrievedAt: "2026-08-12T10:00:00Z",
        },
      ],
    });

    renderApp({ reports: [reportWith({}, [sourcedUpdate])] });

    const kbLink = screen.getByRole("link", {
      name: "Abrir KB5120386 en Microsoft Support",
    });
    expect(kbLink.textContent).toBe("KB5120386");
    expect(kbLink.getAttribute("href")).toBe(
      "https://support.microsoft.com/help/5120386",
    );
    expect(kbLink.getAttribute("target")).toBe("_blank");
    expect(kbLink.getAttribute("rel")).toBe("noreferrer");

    fireEvent.click(screen.getByText("Fuentes (1)"));

    const sourceLink = screen.getByRole("link", {
      name: "Abrir Microsoft Support",
    });
    expect(sourceLink.getAttribute("href")).toBe(
      "https://support.microsoft.com/help/5120386",
    );
  });

  it("keeps the KB as text when no valid Microsoft Support source exists", () => {
    const unsupportedSource = updateWith({
      kb: "KB5120386",
      sources: [
        {
          type: "microsoft-support",
          url: "https://example.com/help/5120386",
          retrievedAt: "2026-08-12T10:00:00Z",
        },
      ],
    });

    renderApp({ reports: [reportWith({}, [unsupportedSource])] });

    expect(
      screen.queryByRole("link", {
        name: "Abrir KB5120386 en Microsoft Support",
      }),
    ).toBeNull();
    expect(
      screen.getByText("KB5120386", { selector: ".kb-number" }),
    ).toBeTruthy();
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

  it("provides a visible report-mode exit outside the exported surface", () => {
    const { container } = renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Modo informe" }));

    const exitButton = screen.getByRole("button", {
      name: "Volver a vista interactiva",
    });
    const reportSurface = container.querySelector<HTMLElement>("#report")!;
    expect(exitButton.textContent).toBe("← Volver");
    expect(reportSurface.contains(exitButton)).toBe(false);

    fireEvent.click(exitButton);

    expect(screen.getByLabelText("Mes del informe")).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "Volver a vista interactiva" }),
    ).toBeNull();
  });

  it("keeps Escape as a report-mode exit shortcut", () => {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Modo informe" }));

    fireEvent.keyDown(window, { key: "Escape" });

    expect(screen.getByLabelText("Mes del informe")).toBeTruthy();
  });

  it("does not link the KB inside Report Mode", () => {
    const sourcedUpdate = updateWith({
      kb: "KB5120386",
      sources: [
        {
          type: "microsoft-support",
          url: "https://support.microsoft.com/help/5120386",
          retrievedAt: "2026-08-12T10:00:00Z",
        },
      ],
    });
    renderApp({ reports: [reportWith({}, [sourcedUpdate])] });
    fireEvent.click(screen.getByRole("button", { name: "Modo informe" }));

    expect(
      screen.queryByRole("link", {
        name: "Abrir KB5120386 en Microsoft Support",
      }),
    ).toBeNull();
    expect(
      screen.getByText("KB5120386", { selector: ".kb-number" }),
    ).toBeTruthy();
  });

  it("switches between locally available report months", () => {
    const { container } = renderApp({
      reports: [julyReport, augustReport],
    });
    const monthSelector =
      screen.getByLabelText<HTMLSelectElement>("Mes del informe");

    expect(monthSelector.value).toBe("2026-08");
    expect(
      screen
        .getAllByRole<HTMLOptionElement>("option")
        .map((option) => option.textContent),
    ).toEqual(["agosto de 2026", "julio de 2026"]);

    fireEvent.change(screen.getByLabelText("Mes del informe"), {
      target: { value: "2026-07" },
    });

    expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
    expect(screen.getByText("KB5000001")).toBeTruthy();
    expect(
      screen.getByLabelText("Sistemas operativos: 1 de 1 seleccionados"),
    ).toBeTruthy();
  });

  it("keeps OS selection valid when the report month changes", () => {
    const { container } = renderApp({ reports: [augustReport, julyReport] });

    fireEvent.click(screen.getByRole("button", { name: "Limpiar" }));
    fireEvent.click(
      screen.getByRole("checkbox", { name: "Windows Server 2025" }),
    );
    fireEvent.change(screen.getByLabelText("Mes del informe"), {
      target: { value: "2026-07" },
    });

    expect(screen.getAllByRole<HTMLInputElement>("checkbox")).toHaveLength(1);
    expect(screen.getByRole<HTMLInputElement>("checkbox").checked).toBe(true);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
    expect(screen.getByText("KB5000001")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Mes del informe"), {
      target: { value: "2026-08" },
    });
    expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
    expect(screen.getByText("KB5120233")).toBeTruthy();
  });

  it("carries the selected month into Report Mode", () => {
    const { container } = renderApp({ reports: [augustReport, julyReport] });
    fireEvent.change(screen.getByLabelText("Mes del informe"), {
      target: { value: "2026-07" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Modo informe" }));

    expect(screen.getByText("Informe mensual · julio de 2026")).toBeTruthy();
    expect(screen.getByText("14 de julio de 2026")).toBeTruthy();
    expect(screen.getByText("KB5000001")).toBeTruthy();
    expect(container.querySelectorAll("thead th")).toHaveLength(5);
    expect(
      within(container.querySelector(".report-metadata")!).getByText("1"),
    ).toBeTruthy();
  });

  it("shows project and professional links in Interactive Mode", () => {
    renderApp();

    expect(
      screen
        .getByRole("link", { name: "Windows Patch Dashboard" })
        .getAttribute("href"),
    ).toBe("https://f4cus.github.io/windows-patch-dashboard/");
    expect(screen.getByText("Facu Villagra")).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "LinkedIn" }).getAttribute("href"),
    ).toBe("https://www.linkedin.com/in/fvillagra/");
    expect(
      screen.getByRole("link", { name: "GitHub" }).getAttribute("href"),
    ).toBe("https://github.com/f4cus/windows-patch-dashboard");
  });

  it("includes restrained product and author attribution in Report Mode", () => {
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Modo informe" }));

    expect(
      screen.getByText(
        "Windows Patch Dashboard · f4cus.github.io/windows-patch-dashboard",
      ),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "Desarrollado por Facu Villagra · linkedin.com/in/fvillagra",
      ),
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
    expect(exportedReport.textContent).toContain(
      "Desarrollado por Facu Villagra · linkedin.com/in/fvillagra",
    );
    expect(exportedReport.textContent).toContain(
      "Windows Patch Dashboard · f4cus.github.io/windows-patch-dashboard",
    );
  });

  it("exports the selected report month", async () => {
    const exporter = vi.fn().mockResolvedValue(undefined);
    const { container } = renderApp({
      exporter,
      reports: [augustReport, julyReport],
    });
    fireEvent.change(screen.getByLabelText("Mes del informe"), {
      target: { value: "2026-07" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Exportar PNG" }));

    await waitFor(() => expect(exporter).toHaveBeenCalledTimes(1));
    const exportedReport = exporter.mock.calls[0][0] as HTMLElement;
    expect(exportedReport).toBe(container.querySelector("#report"));
    expect(exportedReport.textContent).toContain("julio de 2026");
    expect(exportedReport.textContent).toContain("KB5000001");
    expect(exporter).toHaveBeenCalledWith(
      exportedReport,
      "microsoft-patch-tuesday-2026-07",
    );
  });
});
