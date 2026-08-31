import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

function moduleGroup(moduleId: string): string {
  const normalized = moduleId.replaceAll('\\', '/')
  const nodeModulesIndex = normalized.lastIndexOf('/node_modules/')
  if (nodeModulesIndex >= 0) {
    const packagePath = normalized.slice(nodeModulesIndex + '/node_modules/'.length).split('/')
    return packagePath[0]?.startsWith('@')
      ? `${packagePath[0]}/${packagePath[1] || 'unknown'}`
      : packagePath[0] || 'unknown-package'
  }
  const sourceIndex = normalized.lastIndexOf('/src/')
  if (sourceIndex >= 0) {
    const sourcePath = normalized.slice(sourceIndex + '/src/'.length).split('/')
    return `app:${sourcePath[0] || 'root'}`
  }
  return 'app:other'
}

function bundleCompositionReporter(): Plugin {
  return {
    name: 'shogun-bundle-composition',
    generateBundle(_options, bundle) {
      const chunks = Object.values(bundle)
        .filter(output => output.type === 'chunk')
        .map(chunk => {
          const groups = new Map<string, { bytes: number; modules: number }>()
          for (const [moduleId, moduleInfo] of Object.entries(chunk.modules)) {
            const group = moduleGroup(moduleId)
            const current = groups.get(group) || { bytes: 0, modules: 0 }
            current.bytes += moduleInfo.renderedLength
            current.modules += 1
            groups.set(group, current)
          }
          return {
            fileName: chunk.fileName,
            isEntry: chunk.isEntry,
            isDynamicEntry: chunk.isDynamicEntry,
            renderedBytes: Object.values(chunk.modules).reduce(
              (total, moduleInfo) => total + moduleInfo.renderedLength,
              0,
            ),
            groups: [...groups.entries()]
              .map(([name, value]) => ({ name, ...value }))
              .sort((left, right) => right.bytes - left.bytes),
          }
        })
        .sort((left, right) => right.renderedBytes - left.renderedBytes)

      this.emitFile({
        type: 'asset',
        fileName: 'bundle-composition.json',
        source: JSON.stringify({ generatedAt: new Date().toISOString(), chunks }, null, 2),
      })
    },
  }
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss(), ...(mode === 'analyze' ? [bundleCompositionReporter()] : [])],
  build: {
    chunkSizeWarningLimit: 500,
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: 'framework-react',
              test: /node_modules[\\/](?:react|react-dom|scheduler)[\\/]/,
              priority: 50,
            },
            {
              name: 'framework-router',
              test: /node_modules[\\/](?:react-router|react-router-dom)[\\/]/,
              priority: 45,
            },
            {
              name: 'http-client',
              test: /node_modules[\\/]axios[\\/]/,
              priority: 40,
            },
            {
              name: 'flow-graph',
              test: /node_modules[\\/](?:@xyflow[\\/](?:react|system)|d3-[^\\/]+|zustand|use-sync-external-store|classcat)[\\/]/,
              priority: 35,
              maxSize: 240 * 1024,
            },
            {
              name: 'data-formats',
              test: /node_modules[\\/]js-yaml[\\/]/,
              priority: 30,
            },
            {
              name: 'vendor-shared',
              test: /node_modules[\\/]/,
              minShareCount: 2,
              minSize: 20 * 1024,
              maxSize: 240 * 1024,
              entriesAware: true,
              entriesAwareMergeThreshold: 20 * 1024,
              priority: 10,
            },
          ],
        },
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/uploads': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/mado/screenshots': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  }
}))
