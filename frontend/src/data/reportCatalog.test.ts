import { describe, expect, it } from "vitest";
import augustFixture from "../../../data/fixtures/2026-08.json";
import { createReportCatalog } from "./reportCatalog";

describe("local report catalog", () => {
  it("derives months from local files and prefers reports over fixtures", () => {
    const verifiedAugust = {
      ...augustFixture,
      generatedAt: "2026-08-12T10:00:00Z",
      status: "verified",
      updates: augustFixture.updates.map((update) => ({
        ...update,
        sources: [
          {
            type: "microsoft-support",
            url: "https://support.microsoft.com/help/5120386",
            retrievedAt: "2026-08-12T09:00:00Z",
          },
        ],
      })),
    };

    const catalog = createReportCatalog({
      "../../../data/fixtures/2026-08.json": augustFixture,
      "../../../data/reports/2026-08.json": verifiedAugust,
    });

    expect(catalog).toHaveLength(1);
    expect(catalog[0].status).toBe("verified");
  });
});
