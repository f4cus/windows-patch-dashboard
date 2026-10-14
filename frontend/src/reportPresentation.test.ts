import { afterEach, describe, expect, it, vi } from "vitest";
import {
  formatCompactDate,
  formatDate,
  formatDateTime,
  formatReportMonth,
} from "./reportPresentation";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("formatDateTime", () => {
  it.each([
    ["2026-10-14T00:41:29.068022Z", "13-oct-2026, 21:41 (UTC-3)"],
    ["2026-10-14T02:59:59Z", "13-oct-2026, 23:59 (UTC-3)"],
    ["2026-10-14T03:00:00Z", "14-oct-2026, 00:00 (UTC-3)"],
    ["2026-10-14T03:01:00Z", "14-oct-2026, 00:01 (UTC-3)"],
    ["2026-01-01T02:59:59Z", "31-dic-2025, 23:59 (UTC-3)"],
    ["2026-02-01T02:59:59Z", "31-ene-2026, 23:59 (UTC-3)"],
    ["2026-01-05T12:04:00Z", "05-ene-2026, 09:04 (UTC-3)"],
  ])("formats %s as %s", (timestamp, expected) => {
    expect(formatDateTime(timestamp)).toBe(expected);
  });

  it("preserves the null fallback", () => {
    expect(formatDateTime(null)).toBe("No disponible");
  });

  it.each(["UTC", "Asia/Tokyo", "America/Los_Angeles"])(
    "ignores the browser default time zone %s",
    async (browserTimeZone) => {
      const OriginalDateTimeFormat = Intl.DateTimeFormat;
      const browserIntl = Object.create(Intl);
      browserIntl.DateTimeFormat = class extends OriginalDateTimeFormat {
        constructor(
          locales?: Intl.LocalesArgument,
          options?: Intl.DateTimeFormatOptions,
        ) {
          super(locales, { timeZone: browserTimeZone, ...options });
        }
      };
      vi.stubGlobal("Intl", browserIntl);
      expect(new Intl.DateTimeFormat().resolvedOptions().timeZone).toBe(
        browserTimeZone,
      );
      vi.resetModules();
      const presentation = await import("./reportPresentation");

      expect(presentation.formatDateTime("2026-10-14T00:41:29.068022Z")).toBe(
        "13-oct-2026, 21:41 (UTC-3)",
      );
      expect(presentation.formatDate("2026-10-13")).toBe(
        "13 de octubre de 2026",
      );
      expect(presentation.formatCompactDate("2026-10-13")).toBe("13/10/2026");
      expect(presentation.formatReportMonth("2026-10")).toBe("octubre de 2026");
    },
  );
});

describe("calendar dates", () => {
  it("preserves KB and Patch Tuesday dates without shifting the day", () => {
    expect(formatDate("2026-10-13")).toBe("13 de octubre de 2026");
    expect(formatCompactDate("2026-10-13")).toBe("13/10/2026");
    expect(formatReportMonth("2026-10")).toBe("octubre de 2026");
  });

  it("preserves null publication date fallbacks", () => {
    expect(formatDate(null)).toBe("No publicado");
    expect(formatCompactDate(null)).toBe("No publicado");
  });
});
