import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import Papa from "papaparse";

export type Company = {
  company_id: string;
  display_name: string;
  name_kana: string;
  legal_name: string;
  securities_code: string;
  corporate_number: string;
  website_url: string;
  edinet_code: string;
  sec_cik: string;
  ticker: string;
  exchange: string;
  country_code: string;
  is_active: string;
};

export type Industry = {
  industry_id: string;
  name: string;
  description: string;
  classification_basis: string;
  is_active: string;
};

export type CompanyIndustry = {
  company_id: string;
  industry_id: string;
};

export type CompanyRelation = {
  from_company_id: string;
  to_company_id: string;
  relation_type: "parent" | "subsidiary" | "affiliate" | "brand" | "other";
  valid_from: string;
  valid_to: string;
  source_id: string;
  note: string;
};

export type Metric = {
  company_id: string;
  metric_key: string;
  fiscal_year: string;
  period_end: string;
  value: string;
  unit: string;
  scope: string;
  accounting_standard: string;
  availability: string;
  source_id: string;
  note: string;
};

export type Segment = {
  company_id: string;
  fiscal_year: string;
  segment_id: string;
  segment_name: string;
  description: string;
  revenue: string;
  segment_profit: string;
  profit_measure: string;
  currency: string;
  unit: string;
  availability: string;
  source_id: string;
  note: string;
};

export type CompanyProfile = {
  company_id: string;
  overview: string;
  career_url: string;
  recruitment_summary: string;
  job_categories: string;
  workplace: string;
  compensation: string;
  employment_note: string;
  updated_at: string;
};

export type CompanyAnnotation = {
  annotation_id: string;
  company_id: string;
  section_key: string;
  target_kind: "section" | "metric_group" | "metric";
  target_key: string;
  fiscal_year: string;
  text: string;
  source_id: string;
  updated_at: string;
};

export type Source = {
  source_id: string;
  source_type: string;
  title: string;
  url: string;
  document_id: string;
  published_at: string;
  retrieved_at: string;
  issuer: string;
};

const cashFlowKeys = [
  "operating_cf",
  "investing_cf",
  "financing_cf",
] as const;

function withNetCashFlow(rows: Metric[]): Metric[] {
  const reportedCashFlows = new Map<string, Map<string, Metric>>();

  for (const row of rows) {
    if (
      row.availability !== "reported" ||
      !cashFlowKeys.includes(row.metric_key as (typeof cashFlowKeys)[number])
    ) {
      continue;
    }

    const groupKey = [
      row.company_id,
      row.fiscal_year,
      row.period_end,
      row.unit,
      row.scope,
      row.accounting_standard,
    ].join("\u0000");
    const group = reportedCashFlows.get(groupKey) ?? new Map<string, Metric>();
    group.set(row.metric_key, row);
    reportedCashFlows.set(groupKey, group);
  }

  const netCashFlows: Metric[] = [];
  for (const group of reportedCashFlows.values()) {
    const components = cashFlowKeys.map((key) => group.get(key));
    if (components.some((row) => row === undefined)) continue;

    const [operatingCashFlow] = components as Metric[];
    netCashFlows.push({
      ...operatingCashFlow,
      metric_key: "net_cf",
      value: String(
        (components as Metric[]).reduce(
          (sum, row) => sum + Number(row.value),
          0,
        ),
      ),
      note: "営業CF・投資CF・財務CFの合計（サイト算出値）",
    });
  }

  return [...rows, ...netCashFlows];
}

const dataDirectory = new URL("../../../../data/", import.meta.url);

function loadCsv<T>(filename: string): T[] {
  const path = fileURLToPath(new URL(filename, dataDirectory));
  const csv = readFileSync(path, "utf-8");
  const result = Papa.parse<T>(csv, {
    header: true,
    skipEmptyLines: true,
  });

  if (result.errors.length > 0) {
    throw new Error(
      `${filename} の読み込みに失敗しました: ${result.errors
        .map((error) => error.message)
        .join(", ")}`,
    );
  }

  return result.data;
}

export const allCompanies = loadCsv<Company>("companies.csv");
export const companies = allCompanies.filter(
  (company) => company.is_active === "true",
);
export const industries = loadCsv<Industry>("industries.csv").filter(
  (industry) => industry.is_active === "true",
);
export const companyIndustries =
  loadCsv<CompanyIndustry>("company_industries.csv");
export const companyRelations =
  loadCsv<CompanyRelation>("company_relations.csv");
export const metrics = withNetCashFlow(loadCsv<Metric>("metrics.csv"));
export const segments = loadCsv<Segment>("segments.csv");
export const companyProfiles = loadCsv<CompanyProfile>("company_profiles.csv");
export const companyAnnotations = loadCsv<CompanyAnnotation>(
  "company_annotations.csv",
);
export const sources = loadCsv<Source>("sources.csv");

export function companiesForIndustry(industryId: string): Company[] {
  const ids = new Set(
    companyIndustries
      .filter((relation) => relation.industry_id === industryId)
      .map((relation) => relation.company_id),
  );
  return companies.filter((company) => ids.has(company.company_id));
}

export function metricsForCompanies(companyIds: string[]): Metric[] {
  const ids = new Set(companyIds);
  return metrics.filter(
    (metric) =>
      ids.has(metric.company_id) && metric.availability === "reported",
  );
}

export function sourceById(sourceId: string): Source | undefined {
  return sources.find((source) => source.source_id === sourceId);
}

export function profileForCompany(
  companyId: string,
): CompanyProfile | undefined {
  return companyProfiles.find((profile) => profile.company_id === companyId);
}

const metricGroups: Record<string, string[]> = {
  cash_flow: ["net_cf", "operating_cf", "investing_cf", "financing_cf"],
};

export function annotationsForCompany(companyId: string): CompanyAnnotation[] {
  return companyAnnotations.filter(
    (annotation) => annotation.company_id === companyId,
  );
}

export function annotationTargetsMetric(
  annotation: CompanyAnnotation,
  metricKey: string,
): boolean {
  if (annotation.target_kind === "section") return true;
  if (annotation.target_kind === "metric") {
    return annotation.target_key === metricKey;
  }
  return metricGroups[annotation.target_key]?.includes(metricKey) ?? false;
}
