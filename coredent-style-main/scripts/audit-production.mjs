import { spawnSync } from "node:child_process";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const allowedAdvisories = new Set([
  // react-router server/RSC advisory. Accepted on the condition asserted below:
  // the RSC/server entry points it covers are verified unused in src/.
  "GHSA-qwww-vcr4-c8h2",
  // postcss-selector-parser - uncontrolled AST recursion (low severity).
  // Build-time only: postcss/tailwind run while the bundle is produced and none
  // of this code ships to the browser, so there is no runtime exposure. The
  // in-major fix (6.1.3+) cannot be forced through a package.json "overrides"
  // entry because the package is nested under tailwindcss and postcss-nested,
  // and npm audit fix cannot reach it either. Drop this entry once tailwind
  // pulls 6.1.3 or newer transitively.
  "GHSA-w9m9-85wc-3x92",
]);
const rscPatterns = [
  /react-router-dom\/server/,
  /react-router\/dom/,
  /\bcreateStaticRouter\b/,
  /\bStaticRouter\b/,
  /\bHydratedRouter\b/,
  /\bServerRouter\b/,
  /\bRSCHydratedRouter\b/,
  /\bunstable_[A-Za-z0-9_]*RSC[A-Za-z0-9_]*\b/,
];

const audit = spawnSync("npm", ["audit", "--omit=dev", "--json"], {
  encoding: "utf8",
  shell: process.platform === "win32",
});

if (audit.error) {
  console.error(audit.error.message);
  process.exit(1);
}

let report;
try {
  report = JSON.parse(audit.stdout || "{}");
} catch (error) {
  console.error("Unable to parse npm audit JSON output.");
  console.error(error);
  process.exit(1);
}

const srcDir = fileURLToPath(new URL("../src", import.meta.url));
const sourceFiles = [];

function collectSourceFiles(dir) {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    const stats = statSync(path);
    if (stats.isDirectory()) {
      collectSourceFiles(path);
    } else if (/\.(ts|tsx|js|jsx)$/.test(entry)) {
      sourceFiles.push(path);
    }
  }
}

collectSourceFiles(srcDir);

const rscUsages = [];
for (const file of sourceFiles) {
  const text = readFileSync(file, "utf8");
  for (const pattern of rscPatterns) {
    if (pattern.test(text)) {
      rscUsages.push(relative(process.cwd(), file));
      break;
    }
  }
}

const vulnerabilities = Object.values(report.vulnerabilities ?? {});
const vulnerabilityMap = report.vulnerabilities ?? {};
const unapproved = [];
const approved = [];

function advisoryIdsFor(vulnerability) {
  const advisories = vulnerability.via.filter((via) => typeof via === "object");
  return advisories.map((via) => via.url?.split("/").pop()).filter(Boolean);
}

function isAllowedVulnerability(vulnerability, seen = new Set()) {
  if (seen.has(vulnerability.name)) {
    return true;
  }
  seen.add(vulnerability.name);

  const advisoryIds = advisoryIdsFor(vulnerability);
  const directAdvisoriesAllowed =
    advisoryIds.length === 0 || advisoryIds.every((id) => allowedAdvisories.has(id));
  const transitiveAdvisoriesAllowed = vulnerability.via
    .filter((via) => typeof via === "string")
    .every((name) => {
      const transitive = vulnerabilityMap[name];
      return transitive && isAllowedVulnerability(transitive, seen);
    });

  return directAdvisoriesAllowed && transitiveAdvisoriesAllowed;
}

for (const vulnerability of vulnerabilities) {
  const advisoryIds = advisoryIdsFor(vulnerability);
  const allowed = isAllowedVulnerability(vulnerability);

  if (allowed && rscUsages.length === 0) {
    approved.push(`${vulnerability.name}: ${advisoryIds.join(", ") || "transitive allowed advisory"}`);
  } else {
    unapproved.push({
      name: vulnerability.name,
      severity: vulnerability.severity,
      advisories: advisoryIds,
    });
  }
}

if (rscUsages.length > 0) {
  console.error("React Router RSC/server usage was found, so GHSA-qwww-vcr4-c8h2 is no longer excluded:");
  for (const file of rscUsages) {
    console.error(`- ${file}`);
  }
}

if (unapproved.length > 0 || rscUsages.length > 0) {
  console.error("Production dependency audit failed.");
  for (const item of unapproved) {
    console.error(`- ${item.name} (${item.severity}): ${item.advisories.join(", ") || "transitive advisory"}`);
  }
  process.exit(1);
}

if (approved.length > 0) {
  console.log("Production dependency audit passed with documented SaaS exception(s):");
  for (const item of approved) {
    console.log(`- ${item}`);
  }
} else {
  console.log("Production dependency audit passed with no advisories.");
}
