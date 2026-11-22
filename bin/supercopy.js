#!/usr/bin/env bun

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const exePath = path.join(__dirname, "..", "dist", "SuperCopy.exe");

if (!fs.existsSync(exePath)) {
  console.error(
    [
      "SuperCopy executable not found:",
      `  ${exePath}`,
      "",
      "Build it first:",
      "  bun run build",
      "  # or: npm run build",
      "",
      "From a source checkout this creates dist/SuperCopy.exe.",
      "If you installed via npm/bun, the published package should include dist/SuperCopy.exe.",
    ].join("\n")
  );
  process.exit(1);
}

const args = process.argv.slice(2);

const child = spawn(exePath, args, {
  stdio: "inherit",
  windowsHide: false,
});

child.on("close", (code, signal) => {
  if (signal) {
    process.exit(1);
  }
  process.exit(code == null ? 1 : code);
});

child.on("error", (err) => {
  console.error(`Failed to start SuperCopy executable:\n${err.message || err}`);
  process.exit(1);
});
