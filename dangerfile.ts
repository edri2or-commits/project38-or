/**
 * DangerJS Configuration for 4-Layer Documentation Enforcement
 *
 * This file implements the "Hard Gate" for documentation completeness.
 * Based on: Deep Research - Policy-as-Code Architecture for Autonomous AI Systems (2026)
 *
 * Architecture:
 * - Hard Gate (this file): Deterministic checks that BLOCK PRs
 * - Soft Gate (CodeRabbit): AI semantic verification that WARNS only
 */

import { danger, warn, fail, message, markdown } from "danger";
import { readFileSync, existsSync } from "fs";
import { minimatch } from "minimatch";

// ============================================================================
// Types
// ============================================================================

interface Policy {
  id: string;
  name: string;
  description: string;
  layer: number;
  severity: "fail" | "warn";
  triggers: string[];
  excludes: string[];
  requires: string[];
  message: string;
  threshold_lines?: number;
}

interface PolicyConfig {
  version: string;
  policies: Policy[];
  escape_hatches: {
    labels: string[];
    description: string;
  };
  big_pr_warning: {
    threshold_additions: number;
    threshold_deletions: number;
    message: string;
  };
}

interface ViolationReport {
  policy: Policy;
  triggeredBy: string[];
  missingDocs: string[];
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Check if a file path matches any pattern in a list (glob support)
 */
function matchesPatterns(filePath: string, patterns: string[]): boolean {
  return patterns.some(pattern => {
    // Handle ** glob patterns
    if (pattern.includes("**")) {
      return minimatch(filePath, pattern);
    }
    // Simple contains check for non-glob patterns
    return filePath.includes(pattern.replace("**", "").replace("*", ""));
  });
}

/**
 * Check if a file should be excluded
 */
function isExcluded(filePath: string, excludes: string[]): boolean {
  if (excludes.length === 0) return false;
  return matchesPatterns(filePath, excludes);
}

/**
 * Get all changed files in the PR
 */
function getChangedFiles(): string[] {
  return [
    ...danger.git.modified_files,
    ...danger.git.created_files,
    ...danger.git.deleted_files,
  ];
}

/**
 * Check if PR has an escape hatch label
 */
function hasEscapeHatchLabel(escapeLabels: string[]): boolean {
  const prLabels = danger.github.issue.labels.map(l => l.name.toLowerCase());
  return escapeLabels.some(escape => prLabels.includes(escape.toLowerCase()));
}

/**
 * Calculate total lines changed
 */
function getTotalLinesChanged(): { additions: number; deletions: number } {
  return {
    additions: danger.github.pr.additions,
    deletions: danger.github.pr.deletions,
  };
}

// ============================================================================
// Main Enforcement Logic
// ============================================================================

async function enforceDocumentation() {
  // Load policy configuration
  const policyPath = ".github/doc-policy.json";

  if (!existsSync(policyPath)) {
    fail(":stop_sign: **Configuration Error**: `.github/doc-policy.json` not found.");
    return;
  }

  let config: PolicyConfig;
  try {
    config = JSON.parse(readFileSync(policyPath, "utf8"));
  } catch (e) {
    fail(`:stop_sign: **Configuration Error**: Failed to parse \`.github/doc-policy.json\`: ${e}`);
    return;
  }

  const changedFiles = getChangedFiles();
  const violations: ViolationReport[] = [];

  // Check for escape hatch labels
  if (hasEscapeHatchLabel(config.escape_hatches.labels)) {
    message(`:white_check_mark: **Documentation check skipped** - PR has escape hatch label (${config.escape_hatches.labels.join(", ")})`);
    return;
  }

  // Evaluate each policy
  for (const policy of config.policies) {
    // Find files that trigger this policy
    const triggeredBy = changedFiles.filter(file => {
      const matchesTrigger = matchesPatterns(file, policy.triggers);
      const excluded = isExcluded(file, policy.excludes);
      return matchesTrigger && !excluded;
    });

    // Skip if no triggers matched
    if (triggeredBy.length === 0) continue;

    // Check if threshold applies (for significant changes)
    if (policy.threshold_lines) {
      const { additions, deletions } = getTotalLinesChanged();
      if (additions + deletions < policy.threshold_lines) continue;
    }

    // Check if required files were also modified
    const requirementsMet = policy.requires.some(reqPattern => {
      return changedFiles.some(file => matchesPatterns(file, [reqPattern]));
    });

    if (!requirementsMet) {
      violations.push({
        policy,
        triggeredBy,
        missingDocs: policy.requires,
      });
    }
  }

  // Report violations
  if (violations.length > 0) {
    // Create summary table
    let summaryTable = `
## :page_facing_up: Documentation Enforcement Report

| Layer | Policy | Status | Required Update |
|-------|--------|--------|-----------------|
`;

    for (const v of violations) {
      const statusIcon = v.policy.severity === "fail" ? ":x:" : ":warning:";
      summaryTable += `| L${v.policy.layer} | ${v.policy.name} | ${statusIcon} | \`${v.missingDocs.join("`, `")}\` |\n`;
    }

    summaryTable += `
### Details
`;

    for (const v of violations) {
      summaryTable += `
#### ${v.policy.severity === "fail" ? ":stop_sign:" : ":warning:"} ${v.policy.name}

**Triggered by:** \`${v.triggeredBy.slice(0, 3).join("`, `")}${v.triggeredBy.length > 3 ? "` + " + (v.triggeredBy.length - 3) + " more" : ""}\`

**Message:** ${v.policy.message}

**Required:** Update one of: \`${v.missingDocs.join("`, `")}\`

---
`;
    }

    // Add escape hatch info
    summaryTable += `
> :bulb: **Tip:** Add label \`${config.escape_hatches.labels[0]}\` to skip documentation checks for hotfixes/typos.
`;

    markdown(summaryTable);

    // Apply severity
    for (const v of violations) {
      if (v.policy.severity === "fail") {
        fail(`:stop_sign: **[L${v.policy.layer}] ${v.policy.name}**: ${v.policy.message}`);
      } else {
        warn(`:warning: **[L${v.policy.layer}] ${v.policy.name}**: ${v.policy.message}`);
      }
    }
  } else {
    message(":white_check_mark: **All documentation checks passed!** 4-layer integrity maintained.");
  }

  // Big PR warning
  const { additions, deletions } = getTotalLinesChanged();
  const { threshold_additions, threshold_deletions, message: bigPrMsg } = config.big_pr_warning;

  if (additions > threshold_additions || deletions > threshold_deletions) {
    warn(`:warning: **Large PR** (${additions}+ / ${deletions}-): ${bigPrMsg}`);
  }

  // First-time contributor welcome (DX improvement from Twenty CRM case study)
  const isFirstContribution = danger.github.pr.author_association === "FIRST_TIME_CONTRIBUTOR";
  if (isFirstContribution) {
    message(":wave: Welcome! Thanks for your first contribution. Please ensure documentation is updated for any code changes.");
  }
}

// Run enforcement
enforceDocumentation();
