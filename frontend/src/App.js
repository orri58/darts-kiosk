import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";

// Kiosk Pages
import KioskLayout from "./pages/kiosk/KioskLayout";

// Admin Pages
import AdminLayout from "./pages/admin/AdminLayout";
import AdminLogin from "./pages/admin/Login";
import AdminDashboard from "./pages/admin/Dashboard";
import AdminBoards from "./pages/admin/Boards";
import AdminSettings from "./pages/admin/Settings";
import AdminUsers from "./pages/admin/Users";
import AdminLogs from "./pages/admin/Logs";
import AdminRevenue from "./pages/admin/Revenue";
import AdminHealth from "./pages/admin/Health";
import AdminSystem from "./pages/admin/System";
import AdminDiscovery from "./pages/admin/Discovery";
import AdminLeaderboard from "./pages/admin/Leaderboard";
import AdminReports from "./pages/admin/Reports";
import AdminLicensing from "./pages/admin/Licensing";
import MatchPublicPage from "./pages/MatchPublicPage";
import PublicLeaderboard from "./pages/PublicLeaderboard";
import SetupWizard from "./pages/admin/SetupWizard";
import CreditsOverlay from "./pages/CreditsOverlay";

// Central Portal Pages (previously /operator, now /portal)
import PortalLayout from "./pages/portal/PortalLayout";
import PortalLogin from "./pages/portal/PortalLogin";
import PortalDashboard from "./pages/portal/PortalDashboard";
import PortalDevices from "./pages/portal/PortalDevices";
import PortalLicenses from "./pages/portal/PortalLicenses";
import PortalCustomers from "./pages/portal/PortalCustomers";
import PortalLocations from "./pages/portal/PortalLocations";
import PortalAudit from "./pages/portal/PortalAudit";
import PortalUsers from "./pages/portal/PortalUsers";

// Context
import { AuthProvider } from "./context/AuthContext";
import { SettingsProvider } from "./context/SettingsContext";
import { I18nProvider } from "./context/I18nContext";
import { CentralAuthProvider } from "./context/CentralAuthContext";

function App() {
  return (
    <AuthProvider>
      <SettingsProvider>
        <I18nProvider>
        <CentralAuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Kiosk Routes */}
            <Route path="/kiosk" element={<KioskLayout />} />
            <Route path="/kiosk/:boardId" element={<KioskLayout />} />
            
            {/* Setup Wizard */}
            <Route path="/setup" element={<SetupWizard />} />
            
            {/* Public Match Result */}
            <Route path="/match/:token" element={<MatchPublicPage />} />
            
            {/* Public Leaderboard (for QR on lock screen) */}
            <Route path="/public/leaderboard" element={<PublicLeaderboard />} />
            
            {/* Credits Overlay (opened in separate small window on board PC) */}
            <Route path="/overlay/:boardId" element={<CreditsOverlay />} />
            
            {/* Admin Routes */}
            <Route path="/admin/login" element={<AdminLogin />} />
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<AdminDashboard />} />
              <Route path="boards" element={<AdminBoards />} />
              <Route path="settings" element={<AdminSettings />} />
              <Route path="users" element={<AdminUsers />} />
              <Route path="logs" element={<AdminLogs />} />
              <Route path="revenue" element={<AdminRevenue />} />
              <Route path="health" element={<AdminHealth />} />
              <Route path="system" element={<AdminSystem />} />
              <Route path="discovery" element={<AdminDiscovery />} />
              <Route path="leaderboard" element={<AdminLeaderboard />} />
              <Route path="reports" element={<AdminReports />} />
              <Route path="licensing" element={<AdminLicensing />} />
            </Route>

            {/* Central Portal Routes (/portal) */}
            <Route path="/portal/login" element={<PortalLogin />} />
            <Route path="/portal" element={<PortalLayout />}>
              <Route index element={<PortalDashboard />} />
              <Route path="devices" element={<PortalDevices />} />
              <Route path="licenses" element={<PortalLicenses />} />
              <Route path="customers" element={<PortalCustomers />} />
              <Route path="locations" element={<PortalLocations />} />
              <Route path="users" element={<PortalUsers />} />
              <Route path="audit" element={<PortalAudit />} />
            </Route>

            {/* Legacy /operator redirects → /portal */}
            <Route path="/operator/login" element={<Navigate to="/portal/login" replace />} />
            <Route path="/operator/devices" element={<Navigate to="/portal/devices" replace />} />
            <Route path="/operator/licenses" element={<Navigate to="/portal/licenses" replace />} />
            <Route path="/operator/customers" element={<Navigate to="/portal/customers" replace />} />
            <Route path="/operator/locations" element={<Navigate to="/portal/locations" replace />} />
            <Route path="/operator/users" element={<Navigate to="/portal/users" replace />} />
            <Route path="/operator/audit" element={<Navigate to="/portal/audit" replace />} />
            <Route path="/operator" element={<Navigate to="/portal" replace />} />
            
            {/* Default redirect */}
            <Route path="/" element={<Navigate to="/kiosk" replace />} />
            <Route path="*" element={<Navigate to="/kiosk" replace />} />
          </Routes>
        </BrowserRouter>
        </CentralAuthProvider>
        </I18nProvider>
        <Toaster 
          position="bottom-center" 
          theme="dark"
          toastOptions={{
            style: {
              background: 'hsl(240 6% 10%)',
              border: '1px solid hsl(240 3.7% 15.9%)',
              color: 'hsl(0 0% 89%)',
            },
          }}
        />
      </SettingsProvider>
    </AuthProvider>
  );
}

export default App;
