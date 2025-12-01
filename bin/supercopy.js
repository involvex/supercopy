#!/usr/bin/env node

const path = require('path');
const { spawn } = require('child_process');

// The executable is located in the 'dist' folder, one level above the 'bin' directory.
const exePath = path.join(__dirname, '..', 'dist', 'SuperCopy.exe');

// Pass all command-line arguments to the executable, removing the first two ('node' and the script path).
const args = process.argv.slice(2);

// Spawn the child process.
const child = spawn(exePath, args, {
  // 'inherit' ensures that the child process uses the same stdin, stdout, and stderr
  // as the parent. This is crucial for CLI interaction.
  stdio: 'inherit'
});

// Exit with the same code as the child process.
child.on('close', (code) => {
  process.exit(code);
});

child.on('error', (err) => {
  console.error(`Failed to start SuperCopy executable:\n${err}`);
  process.exit(1);
});
