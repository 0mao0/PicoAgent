import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { execSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { resolve } from 'path'
import portContract from '../shared/ports.json'
import pdfWasmPlugin from '../../packages/docs-ui/vite-pdf-wasm.mjs'

const WEB_CONSOLE_PORT = portContract.webConsolePort
const DOCS_API_PROXY_TARGET = `http://${portContract.localHost}:${portContract.docsApiPort}`
const AICHAT_API_PROXY_TARGET = `http://${portContract.localHost}:${portContract.aichatApiPort}`

function getAppVersion(): string {
  try {
    return execSync('git describe --tags --abbrev=0', { encoding: 'utf-8' }).trim().replace(/^v/, '') || '0.1.0';
  } catch {
    // Docker 等环境无 git，回退读 package.json
    try {
      const pkg = JSON.parse(readFileSync(resolve(__dirname, '../../package.json'), 'utf-8'));
      return pkg.version || '0.1.0';
    } catch {
      return '0.1.0';
    }
  }
}

const APP_VERSION = getAppVersion();

/**
 * 从根 README「当前版本」行提取本版摘要，供顶栏版本号 hover 展示发版内容。
 * 该行按发版约定把本版摘要以「vX.Y.Z <摘要>」追加在行尾；无匹配返回空串（顶栏退化为纯版本号）。
 */
function extractReleaseNotes(version: string): string {
  try {
    const readme = readFileSync(resolve(__dirname, '../../README.md'), 'utf8')
    const line = readme.split(/\r?\n/).find(l => l.includes('当前版本：'))
    if (!line) return ''
    const marker = `v${version} `
    const at = line.lastIndexOf(marker)
    if (at < 0) return ''
    return line.slice(at + marker.length).replace(/。+$/, '').trim()
  } catch {
    return ''
  }
}

const RELEASE_NOTES = extractReleaseNotes(APP_VERSION)

export default defineConfig({
  plugins: [vue(), pdfWasmPlugin()],
  define: {
    'import.meta.env.VITE_APP_VERSION': JSON.stringify(APP_VERSION),
    'import.meta.env.VITE_APP_RELEASE_NOTES': JSON.stringify(RELEASE_NOTES)
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@angineer/ui-kit': resolve(__dirname, '../../packages/ui-kit/src'),
      '@angineer/aichat-ui': resolve(__dirname, '../../packages/aichat-ui/src'),
      '@angineer/docs-ui': resolve(__dirname, '../../packages/docs-ui/src'),
      '@angineer/smartree': resolve(__dirname, '../../packages/smartree/src'),
      '@angineer/sop-ui': resolve(__dirname, '../../packages/sop-ui/src'),
      '@angineer/geo-ui': resolve(__dirname, '../../packages/geo-ui/src'),
      '@angineer/evals-ui': resolve(__dirname, '../../packages/evals-ui/src')
    }
  },
  css: {
    preprocessorOptions: {
      less: {
        javascriptEnabled: true,
        additionalData: `@import "${resolve(__dirname, '../../packages/ui-kit/src/styles/variables.less')}";\n`
      }
    }
  },
  server: {
    host: true,
    port: WEB_CONSOLE_PORT,
    proxy: {
      '/api/knowledge': { target: DOCS_API_PROXY_TARGET, changeOrigin: true },
      '/api/graph': { target: DOCS_API_PROXY_TARGET, changeOrigin: true },
      '/api/v1': { target: DOCS_API_PROXY_TARGET, changeOrigin: true },
      '/api/api-keys': { target: DOCS_API_PROXY_TARGET, changeOrigin: true },
      '/api/chat': { target: AICHAT_API_PROXY_TARGET, changeOrigin: true },
      '/api/sops': { target: AICHAT_API_PROXY_TARGET, changeOrigin: true },
      '/api/evals': { target: AICHAT_API_PROXY_TARGET, changeOrigin: true },
      '/api/dream-cycle': { target: AICHAT_API_PROXY_TARGET, changeOrigin: true },
      '/api/llm_configs': { target: AICHAT_API_PROXY_TARGET, changeOrigin: true },
      '/api': { target: DOCS_API_PROXY_TARGET, changeOrigin: true }
    }
  }
})
