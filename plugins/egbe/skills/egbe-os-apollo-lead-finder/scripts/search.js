#!/usr/bin/env node
"use strict";
require("./lib/sourcing").run("search").then((code) => { process.exitCode = code; }).catch((error) => {
  console.error(`FATAL: ${error.message}`);
  process.exitCode = 1;
});
