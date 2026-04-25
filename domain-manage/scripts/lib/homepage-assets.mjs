import { access, copyFile, mkdir } from "node:fs/promises";
import path from "node:path";

import { homepageGalleryConfig } from "../../config/homepage-gallery.mjs";
import { domainManageDir } from "./workspace-paths.mjs";

const homepageAssetsDir = path.resolve(domainManageDir, "assets/homepage");

export function getHomepageAssetsDir() {
  return homepageAssetsDir;
}

export function getHomepageGalleryAssets() {
  const mobileHero = normalizeHomepageAssetSpec(
    homepageGalleryConfig.mobileHero,
    "mobile-cover",
  );
  const desktopBackgrounds = (homepageGalleryConfig.desktopBackgrounds ?? []).map((item, index) =>
    normalizeHomepageAssetSpec(item, `background-${index + 1}`),
  );
  if (desktopBackgrounds.length === 0) {
    throw new Error("Homepage gallery requires at least one desktop background.");
  }
  return {
    mobileHero,
    desktopBackgrounds,
    all: [mobileHero, ...desktopBackgrounds],
  };
}

export async function verifyHomepageAssets() {
  const assets = getHomepageGalleryAssets();
  const verifiedAssets = [];
  for (const asset of assets.all) {
    verifiedAssets.push(await verifyHomepageAsset(asset));
  }
  return {
    mobileHero: verifiedAssets[0],
    desktopBackgrounds: verifiedAssets.slice(1),
    all: verifiedAssets,
  };
}

export async function copyHomepageAssetsToDist(outputDir) {
  const assets = await verifyHomepageAssets();
  const copiedAssets = [];
  for (const asset of assets.all) {
    copiedAssets.push(await copyHomepageAssetToDir(asset, outputDir));
  }
  return {
    mobileHero: copiedAssets[0],
    desktopBackgrounds: copiedAssets.slice(1),
    all: copiedAssets,
  };
}

export function resolveHomepageAssetPath(relativePath) {
  const normalizedPath = String(relativePath ?? "").trim();
  if (!normalizedPath) {
    throw new Error("Homepage asset path is required.");
  }
  const absolutePath = path.resolve(domainManageDir, normalizedPath);
  const relativeToHomepageAssets = path.relative(homepageAssetsDir, absolutePath);
  if (
    relativeToHomepageAssets.startsWith("..") ||
    path.isAbsolute(relativeToHomepageAssets)
  ) {
    throw new Error(
      `Homepage asset must stay under assets/homepage: ${normalizedPath}`,
    );
  }
  return absolutePath;
}

export function inferHomepageAssetMimeType(filePath) {
  const extension = path.extname(filePath).toLowerCase();
  if (extension === ".png") {
    return "image/png";
  }
  if (extension === ".jpg" || extension === ".jpeg") {
    return "image/jpeg";
  }
  if (extension === ".webp") {
    return "image/webp";
  }
  throw new Error(`Unsupported homepage asset type: ${filePath}`);
}

function normalizeHomepageAssetSpec(rawSpec, fallbackId) {
  if (!rawSpec || typeof rawSpec !== "object") {
    throw new Error(`Invalid homepage asset config: ${fallbackId}`);
  }
  const id = String(rawSpec.id ?? fallbackId).trim() || fallbackId;
  const assetPath = String(rawSpec.assetPath ?? "").trim();
  if (!assetPath) {
    throw new Error(`Homepage assetPath is required for ${id}.`);
  }
  return {
    ...rawSpec,
    id,
    assetPath,
  };
}

async function verifyHomepageAsset(spec) {
  const absolutePath = resolveHomepageAssetPath(spec.assetPath);
  await access(absolutePath);
  return {
    ...spec,
    assetPath: toPosixRelativePath(spec.assetPath),
    absolutePath: absolutePath,
    mimeType: inferHomepageAssetMimeType(absolutePath),
  };
}

async function copyHomepageAssetToDir(asset, outputDir) {
  const destinationPath = path.join(outputDir, ...asset.assetPath.split("/"));
  await mkdir(path.dirname(destinationPath), { recursive: true });
  await copyFile(asset.absolutePath, destinationPath);
  return {
    ...asset,
    outputPath: destinationPath,
    publicPath: `./${asset.assetPath}`,
  };
}

function toPosixRelativePath(filePath) {
  return String(filePath).replaceAll("\\", "/");
}
