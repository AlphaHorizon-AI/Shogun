import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Shell } from './components/layout/Shell'
import { Dashboard } from './pages/Dashboard'
import { Chat } from './pages/Chat'
import { ShogunProfile } from './pages/ShogunProfile'
import { SamuraiNetwork } from './pages/SamuraiNetwork'
import { Katana } from './pages/Katana'
import { Torii } from './pages/Torii'
import { Kaizen } from './pages/Kaizen'
import { Bushido } from './pages/Bushido'
import { Archives } from './pages/Archives'
import { Dojo } from './pages/Dojo'
import { Logs } from './pages/Logs'
import { Guide } from './pages/Guide'

function App() {
  return (
    <Router>
      <Shell>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/shogun" element={<ShogunProfile />} />
          <Route path="/samurai" element={<SamuraiNetwork />} />
          <Route path="/katana" element={<Katana />} />
          <Route path="/torii" element={<Torii />} />
          <Route path="/kaizen" element={<Kaizen />} />
          <Route path="/bushido" element={<Bushido />} />
          <Route path="/archives" element={<Archives />} />
          <Route path="/dojo" element={<Dojo />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/guide" element={<Guide />} />
          {/* Fallback to home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Shell>
    </Router>
  )
}

export default App
