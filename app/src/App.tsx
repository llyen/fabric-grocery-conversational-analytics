import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { AuthPage } from '@/components/AuthPage';
import { Uklad } from '@/components/Uklad';
import { useAuth } from '@/hooks/AuthContext';
import { DanePage } from '@/pages/DanePage';
import { PlanPage } from '@/pages/PlanPage';
import { PulpitPage } from '@/pages/PulpitPage';
import { SygnalyPage } from '@/pages/SygnalyPage';
import { ZapytajPage } from '@/pages/ZapytajPage';

function AuthGuard({ children, requireAuth }: { children: React.ReactNode; requireAuth: boolean }) {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-slate-500">Ładowanie...</div>
      </div>
    );
  }

  if (requireAuth && !isAuthenticated) return <Navigate to="/auth" replace />;
  if (!requireAuth && isAuthenticated) return <Navigate to="/" replace />;

  return <>{children}</>;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/auth"
          element={
            <AuthGuard requireAuth={false}>
              <AuthPage />
            </AuthGuard>
          }
        />
        <Route
          element={
            <AuthGuard requireAuth={true}>
              <Uklad />
            </AuthGuard>
          }
        >
          <Route path="/" element={<PulpitPage />} />
          <Route path="/sygnaly" element={<SygnalyPage />} />
          <Route path="/plan" element={<PlanPage />} />
          <Route path="/dane" element={<DanePage />} />
          <Route path="/zapytaj" element={<ZapytajPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
