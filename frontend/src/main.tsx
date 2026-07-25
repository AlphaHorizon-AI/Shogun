import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import {
  consumeInfrastructureTokenFromLocation,
  installInfrastructureFetchGuard,
} from './lib/infrastructureAuth.ts'

consumeInfrastructureTokenFromLocation()
installInfrastructureFetchGuard()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
