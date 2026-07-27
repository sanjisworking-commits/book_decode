#!/usr/bin/env node
/**
 * Fail if frontend source appears to hardcode Argument Spine chapter claims.
 * Allows UI chrome labels (node type names) but not long claim-like prose in src/.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "src");

const FORBIDDEN = [
  /The author argues that/i,
  /In this chapter the author/i,
  /statement_en:\s*["'][^"']{40,}/,
  /central claim of the book is/i,
];

function walk(dir, files = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, files);
    else if (/\.(tsx?|jsx?)$/.test(entry.name)) files.push(full);
  }
  return files;
}

const files = walk(root);
const violations = [];

for (const file of files) {
  const rel = path.relative(root, file);
  const text = fs.readFileSync(file, "utf8");
  for (const re of FORBIDDEN) {
    if (re.test(text)) {
      violations.push(`${rel} matches ${re}`);
    }
  }
}

if (violations.length) {
  console.error("Hardcoded spine content check failed:");
  for (const v of violations) console.error(" -", v);
  process.exit(1);
}

console.log(`OK: scanned ${files.length} files, no hardcoded spine claims.`);
