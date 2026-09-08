// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { exportReportAsPng, type PngRenderer } from "./exportReport";

describe("PNG export", () => {
  beforeEach(() => {
    Object.defineProperty(document, "fonts", {
      configurable: true,
      value: { ready: Promise.resolve() },
    });
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
  });

  afterEach(() => {
    document.body.replaceChildren();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("renders the exact report node at high resolution and downloads it", async () => {
    const report = document.createElement("article");
    report.style.backgroundColor = "oklch(98.5% 0.004 250)";
    Object.defineProperties(report, {
      scrollWidth: { configurable: true, value: 1600 },
      scrollHeight: { configurable: true, value: 900 },
    });
    document.body.append(report);

    const renderer = vi.fn().mockResolvedValue("data:image/png;base64,report");
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);

    await exportReportAsPng(report, "patch-report", renderer);

    expect(renderer).toHaveBeenCalledWith(
      report,
      expect.objectContaining({
        cacheBust: true,
        height: 900,
        pixelRatio: 2,
        width: 1600,
      }),
    );
    expect(click).toHaveBeenCalledTimes(1);
    expect(report.dataset.exporting).toBeUndefined();
  });

  it("excludes the footer subtree while retaining normal report nodes", async () => {
    const report = document.createElement("article");
    report.innerHTML = `
      <header>Microsoft Patch Tuesday</header>
      <table><tbody><tr><td>Report content</td></tr></tbody></table>
      <footer class="report-footer"><span>Author credits</span><a href="https://www.linkedin.com/">LinkedIn</a></footer>
    `;
    document.body.append(report);
    const originalMarkup = report.innerHTML;
    const footer = report.querySelector("footer")!;
    const renderer = vi
      .fn<PngRenderer>()
      .mockImplementation(async (node, options) => {
        expect(node.dataset.exporting).toBe("true");
        expect(options?.filter).toBeTypeOf("function");
        // html-to-image visits all node types despite its HTMLElement signature.
        const filter = options!.filter as (candidate: Node) => boolean;
        expect(filter(footer)).toBe(false);
        for (const content of report.querySelectorAll(
          "header, table, tbody, tr, td",
        )) {
          expect(filter(content)).toBe(true);
        }
        // The renderer also visits text and SVG nodes; keep normal content intact.
        expect(filter(report.querySelector("td")!.firstChild!)).toBe(true);
        expect(
          filter(document.createElementNS("http://www.w3.org/2000/svg", "svg")),
        ).toBe(true);
        expect(footer.isConnected).toBe(true);
        expect(report.innerHTML).toBe(originalMarkup);
        return "data:image/png;base64,report";
      });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      () => undefined,
    );

    await exportReportAsPng(report, "patch-report", renderer);

    expect(renderer).toHaveBeenCalledTimes(1);
    expect(report.innerHTML).toBe(originalMarkup);
    expect(report.dataset.exporting).toBeUndefined();
  });

  it.each([undefined, "false", "true"])(
    "restores export state %s after success or renderer failure",
    async (previousState) => {
      const report = document.createElement("article");
      report.innerHTML =
        '<footer class="report-footer">Author credits</footer>';
      if (previousState !== undefined) report.dataset.exporting = previousState;
      document.body.append(report);
      const originalMarkup = report.outerHTML;
      const click = vi
        .spyOn(HTMLAnchorElement.prototype, "click")
        .mockImplementation(() => undefined);
      const failure = new Error("PNG renderer failed");

      for (const fails of [false, true]) {
        const renderer = vi
          .fn<PngRenderer>()
          .mockImplementation(async (node) => {
            expect(node.dataset.exporting).toBe("true");
            if (fails) throw failure;
            return "data:image/png;base64,report";
          });
        const result = exportReportAsPng(report, "patch-report", renderer);
        if (fails) await expect(result).rejects.toBe(failure);
        else await result;

        expect(renderer).toHaveBeenCalledTimes(1);
        expect(report.outerHTML).toBe(originalMarkup);
      }
      expect(click).toHaveBeenCalledTimes(1);
    },
  );
});
