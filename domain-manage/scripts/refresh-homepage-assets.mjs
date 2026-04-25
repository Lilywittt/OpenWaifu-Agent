throw new Error(
  "Homepage assets are now curated files under assets/homepage and this script no longer rewrites them. Use `node ./scripts/check-homepage-assets.mjs` to verify assets, then `npm run build` to regenerate dist output.",
);
