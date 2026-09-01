// No bundler: this is an ES module the browser loads directly.
// Imports of other local modules work as-is — use relative paths with the
// extension ("./thing.js"), since there is no resolver to guess them for you.

const out = document.getElementById("out");

document.getElementById("ping").addEventListener("click", () => {
  out.textContent = `hello at ${new Date().toLocaleTimeString()}`;
});
