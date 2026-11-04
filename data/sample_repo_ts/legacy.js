const fs = require("node:fs");

function render(value) {
  document.body.innerHTML = value;
}

function run(command) {
  require("child_process").execSync(`rm -rf ${command}`);
  return fs.existsSync(command);
}

module.exports = { render, run };
