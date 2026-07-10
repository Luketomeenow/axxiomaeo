import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { BrandSettingsPage } from "./pages/BrandSettingsPage";
import { CitationsPage } from "./pages/CitationsPage";
import { ContentQueuePage } from "./pages/ContentQueuePage";
import { ContentReviewDetailPage } from "./pages/ContentReviewDetailPage";
import { ContentReviewPage } from "./pages/ContentReviewPage";
import { PublishedContentPage } from "./pages/PublishedContentPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DocumentationPage } from "./pages/DocumentationPage";
import { LoginPage } from "./pages/LoginPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { RecommendationsPage } from "./pages/RecommendationsPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SchemaHealthPage } from "./pages/SchemaHealthPage";
import { PublishedSchemaPage } from "./pages/PublishedSchemaPage";
import { SchemaReviewPage } from "./pages/SchemaReviewPage";
import { supabase } from "./lib/supabase";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30000 } },
});

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-void">
        <p className="text-muted">Loading…</p>
      </div>
    );
  }

  if (!supabase) {
    return <>{children}</>;
  }

  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/recommendations" element={<RecommendationsPage />} />
        <Route path="/content/review" element={<ContentReviewPage />} />
        <Route path="/content/review/:id" element={<ContentReviewDetailPage />} />
        <Route path="/content/published" element={<PublishedContentPage />} />
        <Route path="/content/queue" element={<ContentQueuePage />} />
        <Route path="/schema/review" element={<SchemaReviewPage />} />
        <Route path="/schema/published" element={<PublishedSchemaPage />} />
        <Route path="/citations" element={<CitationsPage />} />
        <Route path="/schema/health" element={<SchemaHealthPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/settings/brands" element={<BrandSettingsPage />} />
        <Route path="/settings/brands/:brandId" element={<BrandSettingsPage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/docs" element={<DocumentationPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
