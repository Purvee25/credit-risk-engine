import React, { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { SiteLayout, Landing } from "./Site.jsx";
import ErrorBoundary from "./ErrorBoundary.jsx";

// Lazy-load the console so its heavy bundle stays off the landing page.
const Dashboard = lazy(() => import("./Dashboard.jsx"));

const Loading = () => (
  <div className="boot">
    <div className="boot-mark">◆</div>
    <p>Loading…</p>
  </div>
);

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <Routes>
          <Route element={<SiteLayout />}>
            <Route path="/" element={<Landing />} />
          </Route>
          <Route
            path="/app"
            element={
              <Suspense fallback={<Loading />}>
                <Dashboard />
              </Suspense>
            }
          />
          {/* Retired marketing pages -> home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </ErrorBoundary>
    </BrowserRouter>
  );
}
