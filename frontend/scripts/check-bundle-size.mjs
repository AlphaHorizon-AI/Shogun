import { readdir, stat } from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'

const limitKiB = 500
const limitBytes = limitKiB * 1024
const assetsDirectory = path.resolve('dist', 'assets')
const assetNames = await readdir(assetsDirectory)
const javascriptAssets = assetNames.filter(name => name.endsWith('.js'))
const measuredAssets = await Promise.all(
  javascriptAssets.map(async name => ({
    name,
    bytes: (await stat(path.join(assetsDirectory, name))).size,
  })),
)
const oversizedAssets = measuredAssets
  .filter(asset => asset.bytes > limitBytes)
  .sort((left, right) => right.bytes - left.bytes)
const largestAsset = measuredAssets.sort((left, right) => right.bytes - left.bytes)[0]

if (oversizedAssets.length) {
  console.error(`JavaScript bundle limit exceeded (${limitKiB} KiB):`)
  for (const asset of oversizedAssets) {
    console.error(`- ${asset.name}: ${(asset.bytes / 1024).toFixed(2)} KiB`)
  }
  process.exitCode = 1
} else {
  console.log(
    `Bundle size check passed: ${javascriptAssets.length} JavaScript chunks; largest is `
      + `${largestAsset?.name || 'none'} (${((largestAsset?.bytes || 0) / 1024).toFixed(2)} KiB).`,
  )
}
