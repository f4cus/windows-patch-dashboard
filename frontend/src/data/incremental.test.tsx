// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import november from "../../../data/reports/2026-11.json";
import october from "../../../data/reports/2026-10.json";
import { ClientReport } from "../ClientReport";
import { ReportSurface } from "../ReportSurface";
import { loadMonthlyReport } from "./loadMonthlyReport";

afterEach(cleanup);

// Synthetic absence scenario: actual official November exceptions are tested separately.
function absenceScenario() {
  return {
    ...structuredClone(november),
    status: "generated",
    updates: november.updates.map((row) =>
      row.os.channel === "ESU"
        ? {
            ...row,
            kb: "NO PUBLICADO",
            updateType: "unknown",
            releaseDate: null,
            publicationStatus: "not-published",
            knownIssuesStatus: "unknown",
            supersededBy: null,
            changesSummary:
              "Microsoft finalizó el programa ESU el 13/10/2026. Se recomienda migrar.",
            resolvedIssuesSummary: "No disponible: no hay actualización.",
            knownIssuesSummary: "No disponible: no hay actualización.",
            sources: row.sources.filter(
              (source) => source.type === "lifecycle",
            ),
            verification: undefined,
          }
        : row,
    ),
  };
}

describe("incremental publication contract", () => {
  it("does not claim absence when Microsoft documents exceptional post-ESU updates", () => {
    const report = loadMonthlyReport(november);
    const exceptional = report.updates.filter(
      (row) => row.os.channel === "ESU",
    );
    expect(exceptional).toHaveLength(2);
    expect(
      exceptional.every(
        (row) =>
          row.kb.startsWith("KB") &&
          row.updateType === "oob" &&
          row.releaseDate === "2026-11-06" &&
          row.lifecycle?.status === "esu-ended",
      ),
    ).toBe(true);
    render(
      <ReportSurface
        report={report}
        updates={report.updates}
        scopeLabel="Todos"
        interactive
        theme="light"
      />,
    );
    for (const row of exceptional) {
      expect(
        screen
          .getByRole("link", { name: `Abrir ${row.kb} en Microsoft Support` })
          .getAttribute("href")
          ?.toLowerCase(),
      ).toContain(row.kb.toLowerCase());
    }
    expect(screen.queryByText("SIN ACTUALIZACIÓN — ESU FINALIZADO")).toBeNull();
  });
  it("loads lifecycle separately from publication and known issues", () => {
    const report = loadMonthlyReport(absenceScenario());
    expect(report.schemaVersion).toBe("1.1.0");
    expect(report.status).toBe("generated");
    const ended = report.updates.filter((row) => row.lifecycle);
    expect(ended).toHaveLength(2);
    expect(
      ended.every(
        (row) =>
          row.publicationStatus === "not-published" &&
          row.knownIssuesStatus === "unknown",
      ),
    ).toBe(true);
    expect(
      ended.every((row) =>
        row.sources.some((s) => s.type === "lifecycle" && s.retrievedAt),
      ),
    ).toBe(true);
  });

  it("preserves historical 1.0 reports and rejects lifecycle before its effective month", () => {
    const old = loadMonthlyReport(october);
    expect(old.schemaVersion).toBe("1.0.0");
    expect(old.updates.every((row) => !row.lifecycle)).toBe(true);
    const invalid = structuredClone(november);
    invalid.reportMonth = "2026-10";
    expect(() => loadMonthlyReport(invalid)).toThrow(/ESU lifecycle/u);
  });

  it("rejects a complete report that contains pending evidence", () => {
    const invalid = structuredClone(november);
    invalid.status = "generated";
    invalid.updates[2].publicationStatus = "pending";
    expect(() => loadMonthlyReport(invalid)).toThrow(/partial report/u);
  });

  it("accepts pending candidates without inventing a release date or update type", () => {
    const raw = structuredClone(november);
    raw.status = "partial";
    Object.assign(raw.updates[2], {
      publicationStatus: "pending",
      updateType: "unknown",
      releaseDate: null,
      knownIssuesStatus: "unknown",
      supersededBy: null,
    });
    const report = loadMonthlyReport(raw);
    expect(
      report.updates.find((row) => row.kb === raw.updates[2].kb)?.releaseDate,
    ).toBeNull();
    Object.assign(raw.updates[2], { supersededBy: "KB5000001" });
    expect(() => loadMonthlyReport(raw)).toThrow(/supersedence/u);
  });

  it.each([true, false])(
    "keeps five columns and the ESU explanation (interactive=%s)",
    (interactive) => {
      const report = loadMonthlyReport(absenceScenario());
      render(
        <ReportSurface
          report={report}
          updates={report.updates}
          scopeLabel="Todos"
          interactive={interactive}
          theme="light"
        />,
      );
      expect(screen.getAllByRole("columnheader")).toHaveLength(5);
      expect(
        screen.getAllByText("SIN ACTUALIZACIÓN — ESU FINALIZADO"),
      ).toHaveLength(2);
      expect(screen.queryByText("NO PUBLICADO")).toBeNull();
      expect(screen.queryByText("No verificado")).toBeNull();
    },
  );

  it("uses lifecycle labels in the printable client report", () => {
    const report = loadMonthlyReport(absenceScenario());
    render(
      <ClientReport
        report={report}
        updates={report.updates}
        scopeLabel="Todos"
      />,
    );
    expect(
      screen.getAllByText("SIN ACTUALIZACIÓN — ESU FINALIZADO").length,
    ).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("NO PUBLICADO")).toBeNull();
    expect(screen.queryByText("No verificado")).toBeNull();
  });
});
