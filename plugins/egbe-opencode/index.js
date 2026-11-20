// The package entry exports only the plugin: OpenCode 1.x reads `server()` and
// OpenCode 2.x reads `id` and `setup()` from it. See plugin.js.
import plugin from "./plugin.js";

export default plugin;
