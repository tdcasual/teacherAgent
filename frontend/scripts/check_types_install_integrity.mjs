#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

function parseArgs(argv) {
  const args = { typesDir: "" };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === "--types-dir") {
      args.typesDir = argv[i + 1] || "";
      i += 1;
    }
  }
  return args;
}

function findSuspiciousDirectories(typesDir) {
  const entries = fs.readdirSync(typesDir, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isDirectory() && /\s\d+$/.test(entry.name))
    .map((entry) => entry.name)
    .sort();
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const typesDir = path.resolve(args.typesDir || path.join(process.cwd(), "node_modules", "@types"));

  if (!fs.existsSync(typesDir)) {
    console.error(`[types-guard] Missing directory: ${typesDir}`);
    console.error("[types-guard] Install dependencies first (for example: npm ci).");
    return 1;
  }

  const suspicious = findSuspiciousDirectories(typesDir);
  if (!suspicious.length) {
    console.log(`[types-guard] OK: ${typesDir}`);
    return 0;
  }

  console.error(`[types-guard] Detected suspicious @types directories in ${typesDir}:`);
  for (const name of suspicious) {
    console.error(`  - ${name}`);
  }
  console.error("[types-guard] This usually means node_modules was polluted by a broken install.");
  console.error("[types-guard] Recommended fix: rm -rf node_modules && npm ci");
  return 2;
}

process.exit(main());
