import { Navigate, Route, Routes } from "react-router-dom";
import { BookMapPage } from "./pages/BookMapPage";
import { LandingPage } from "./pages/LandingPage";
import { ProcessingPage } from "./pages/ProcessingPage";
import { SpinePage } from "./pages/SpinePage";
import { UploadPage } from "./pages/UploadPage";

export default function App() {
  return (
    <div className="app-shell">
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/books/:bookId/processing" element={<ProcessingPage />} />
        <Route path="/books/:bookId/map" element={<BookMapPage />} />
        <Route path="/books/:bookId/chapters/:chapterId" element={<SpinePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
