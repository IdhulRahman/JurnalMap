import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { SettingsProvider } from "@/store/settings";
import ProjectsPage from "@/pages/ProjectsPage";
import ProjectPage from "@/pages/ProjectPage";
import DocumentReader from "@/pages/DocumentReader";
import SettingsPage from "@/pages/SettingsPage";

function App() {
  return (
    <div className="App">
      <SettingsProvider>
        <Toaster position="top-right" richColors />
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<ProjectsPage />} />
            <Route path="/project/:id" element={<ProjectPage />} />
            <Route path="/project/:projectId/doc/:docId" element={<DocumentReader />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </BrowserRouter>
      </SettingsProvider>
    </div>
  );
}

export default App;
