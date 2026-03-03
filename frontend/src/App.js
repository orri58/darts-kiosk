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
import SetupWizard from "./pages/admin/SetupWizard";

// Context
import { AuthProvider } from "./context/AuthContext";
import { SettingsProvider } from "./context/SettingsContext";

function App() {
  return (
    <AuthProvider>
      <SettingsProvider>
        <BrowserRouter>
          <Routes>
            {/* Kiosk Routes */}
            <Route path="/kiosk" element={<KioskLayout />} />
            <Route path="/kiosk/:boardId" element={<KioskLayout />} />
            
            {/* Setup Wizard */}
            <Route path="/setup" element={<SetupWizard />} />
            
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
            </Route>
            
            {/* Default redirect */}
            <Route path="/" element={<Navigate to="/kiosk" replace />} />
            <Route path="*" element={<Navigate to="/kiosk" replace />} />
          </Routes>
        </BrowserRouter>
        <Toaster 
          position="top-center" 
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
