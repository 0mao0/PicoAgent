// 版本同步：从 git tag 派生版本号，自动更新 README.md 和 package.json。
//
// 用法：
//   node scripts/sync-version.mjs                  # 从 git tag 同步并更新文件
//   node scripts/sync-version.mjs v0.2.39          # 同步到指定版本
//   node scripts/sync-version.mjs --print-only     # 只打印版本，不修改文件
//
// 发版流程：
//   git tag v0.2.39 && node scripts/sync-version.mjs v0.2.39
//   （脚本自动更新 README.md + package.json + 校验一致性）
import { execSync } from 'child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const ROOT = resolve(__dirname, '..');

function getGitTag() {
  try {
    return execSync('git describe --tags --abbrev=0', { cwd: ROOT, encoding: 'utf-8' }).trim();
  } catch {
    throw new Error('无法获取 git tag，请先执行: git tag vX.Y.Z');
  }
}

function getVersionFromArgs() {
  const args = process.argv.slice(2);
  const versionArg = args.find(a => /^v\d+\.\d+\.\d+$/.test(a));
  if (versionArg) return versionArg;
  return null;
}

function getVersion() {
  const argVersion = getVersionFromArgs();
  if (argVersion) return argVersion;
  return getGitTag();
}

function updateReadme(version) {
  const readmePath = resolve(ROOT, 'README.md');
  const content = readFileSync(readmePath, 'utf-8');
  const lines = content.split(/\r?\n/);

  // 找到包含「当前版本」的行
  const versionLineIdx = lines.findIndex(l => l.includes('当前版本：'));
  if (versionLineIdx < 0) {
    throw new Error('README.md 未找到「当前版本」行');
  }

  const existing = lines[versionLineIdx];
  // 从行中提取版本号：格式为 '当前版本：vX.Y.Z' 或 '当前版本：X.Y.Z'
  const versionInLine = existing.match(/v?\d+\.\d+\.\d+/);
  if (!versionInLine) {
    throw new Error('无法从当前版本行提取版本号');
  }

  // 只替换版本号部分，保留行其余内容
  const newLine = existing.replace(
    /v?\d+\.\d+\.\d+/,
    version.replace(/^v/, '')
  );
  lines[versionLineIdx] = newLine;
  return lines.join('\n');
}

function updatePackageJson(version) {
  const pkgPath = resolve(ROOT, 'package.json');
  const pkg = JSON.parse(readFileSync(pkgPath, 'utf-8'));
  pkg.version = version.replace(/^v/, '');
  return JSON.stringify(pkg, null, 2) + '\n';
}

function checkConsistency(version) {
  const readmePath = resolve(ROOT, 'README.md');
  const pkgPath = resolve(ROOT, 'package.json');
  const readmeContent = readFileSync(readmePath, 'utf-8');
  const pkg = JSON.parse(readFileSync(pkgPath, 'utf-8'));
  // 提取版本号：支持 '当前版本：vX.Y.Z' 或 '当前版本：X.Y.Z' 两种格式
  const readmeVersion = readmeContent.match(/当前版本：v?(\d+\.\d+\.\d+)/)?.[1];

  return {
    readmeOk: readmeVersion === version.replace(/^v/, ''),
    pkgOk: pkg.version === version.replace(/^v/, ''),
  };
}

function main() {
  const version = getVersion();

  console.log(`[sync-version] 版本: ${version}`);

  // 更新 README.md
  const newReadme = updateReadme(version);
  writeFileSync(resolve(ROOT, 'README.md'), newReadme, 'utf-8');
  console.log(`[sync-version] README.md 已更新 → ${version}`);

  // 更新 package.json
  const newPkg = updatePackageJson(version);
  writeFileSync(resolve(ROOT, 'package.json'), newPkg, 'utf-8');
  console.log(`[sync-version] package.json 已更新 → ${version}`);

  // 校验一致性
  const consistency = checkConsistency(version);
  if (!consistency.readmeOk || !consistency.pkgOk) {
    console.error('[sync-version] 一致性校验失败:');
    if (!consistency.readmeOk) console.error('  README.md 版本不匹配');
    if (!consistency.pkgOk) console.error('  package.json 版本不匹配');
    process.exit(1);
  }
  console.log('[sync-version] 三处版本一致: README.md / package.json / git tag');
}

// 仅打印版本（不修改文件）
if (process.argv.includes('--print-only')) {
  console.log(getVersion());
} else {
  main();
}
