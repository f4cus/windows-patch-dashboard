// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";
import { exportReportAsPng } from "./exportReport";

describe("PNG export", () => {
  afterEach(() => {
    document.body.replaceChildren();
    vi.restoreAllMocks();
  });

  it("renders the exact report node at high resolution and downloads it", async () => {
    const report = document.createElement("article");
    report.style.backgroundColor = "oklch(98.5% 0.004 250)";
    Object.defineProperties(report, {
      scrollWidth: { configurable: true, value: 1600 },
      scrollHeight: { configurable: true, value: 900 },
    });
    document.body.append(report);

    Object.defineProperty(document, "fonts", {
      configurable: true,
      value: { ready: Promise.resolve() },
    });
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });

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
});
