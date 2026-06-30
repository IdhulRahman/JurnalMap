import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import ProjectsPage from "@/pages/ProjectsPage";
import ProjectPage from "@/pages/ProjectPage";
import DocumentReader from "@/pages/DocumentReader";

function App() {
  return (
    <div className="App">
      <Toaster position="top-right" richColors />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<ProjectsPage />} />
          <Route path="/project/:id" element={<ProjectPage />} />
          <Route path="/project/:projectId/doc/:docId" element={<DocumentReader />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
