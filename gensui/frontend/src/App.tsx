import { BrowserRouter, Switch, Route, Redirect } from 'react-router-dom';
import { I18nProvider } from './i18n';
import { isAuthenticated } from './lib/auth';
import Layout from './components/layout/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Fleet from './pages/Fleet';
import ShogunDetail from './pages/ShogunDetail';
import NetworkTopology from './pages/NetworkTopology';
import Groups from './pages/Groups';
import Postures from './pages/Postures';
import HarakiriControl from './pages/HarakiriControl';
import ActivityMonitor from './pages/ActivityMonitor';
import AuditLog from './pages/AuditLog';
import Alerts from './pages/Alerts';
import Enrollment from './pages/Enrollment';
import Settings from './pages/Settings';
import Guide from './pages/Guide';
import FleetAudit from './pages/FleetAudit';
import Identity from './pages/Identity';
import ToolGate from './pages/ToolGate';

function ProtectedPage({ children }: { children: React.ReactNode }) {
  return isAuthenticated() ? <Layout>{children}</Layout> : <Redirect to="/login" />;
}

export default function App() {
  return (
    <I18nProvider>
    <BrowserRouter>
      <Switch>
        <Route path="/login" render={() => <Login />} />
        <Route exact path="/" render={() => <ProtectedPage><Dashboard /></ProtectedPage>} />
        <Route exact path="/fleet" render={() => <ProtectedPage><Fleet /></ProtectedPage>} />
        <Route path="/fleet/:id" render={() => <ProtectedPage><ShogunDetail /></ProtectedPage>} />
        <Route path="/network" render={() => <ProtectedPage><NetworkTopology /></ProtectedPage>} />
        <Route path="/groups" render={() => <ProtectedPage><Groups /></ProtectedPage>} />
        <Route path="/postures" render={() => <ProtectedPage><Postures /></ProtectedPage>} />
        <Route path="/toolgate" render={() => <ProtectedPage><ToolGate /></ProtectedPage>} />
        <Route path="/harakiri" render={() => <ProtectedPage><HarakiriControl /></ProtectedPage>} />
        <Route path="/activity" render={() => <ProtectedPage><ActivityMonitor /></ProtectedPage>} />
        <Route path="/audit" render={() => <ProtectedPage><AuditLog /></ProtectedPage>} />
        <Route path="/alerts" render={() => <ProtectedPage><Alerts /></ProtectedPage>} />
        <Route path="/enrollment" render={() => <ProtectedPage><Enrollment /></ProtectedPage>} />
        <Route path="/settings" render={() => <ProtectedPage><Settings /></ProtectedPage>} />
        <Route path="/guide" render={() => <ProtectedPage><Guide /></ProtectedPage>} />
        <Route path="/fleet-audit" render={() => <ProtectedPage><FleetAudit /></ProtectedPage>} />
        <Route path="/identity" render={() => <ProtectedPage><Identity /></ProtectedPage>} />
        <Route render={() => <Redirect to="/" />} />
      </Switch>
    </BrowserRouter>
    </I18nProvider>
  );
}
