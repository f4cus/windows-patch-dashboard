import augustFixture from "../../../data/fixtures/2026-08.json";
import { loadMonthlyReport } from "./loadMonthlyReport";
import type { MonthlyReport } from "./model";

export function loadAugustReport(): MonthlyReport {
  return loadMonthlyReport(augustFixture);
}
