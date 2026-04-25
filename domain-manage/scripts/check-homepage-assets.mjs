import { verifyHomepageAssets } from "./lib/homepage-assets.mjs";

const assets = await verifyHomepageAssets();

console.log(
  JSON.stringify(
    {
      ok: true,
      mobileHero: assets.mobileHero,
      desktopBackgrounds: assets.desktopBackgrounds,
      assetCount: assets.all.length,
    },
    null,
    2,
  ),
);
