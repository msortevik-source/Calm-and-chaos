import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import Shell from "./components/Shell";
import HomePage from "./pages/HomePage";
import ConversationPage from "./pages/ConversationPage";
import BrainDumpPage from "./pages/BrainDumpPage";
import TrainingPage from "./pages/TrainingPage";
import PatternsPage from "./pages/PatternsPage";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route element={<Shell />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/conversation" element={<ConversationPage />} />
            <Route path="/braindump" element={<BrainDumpPage />} />
            <Route path="/training" element={<TrainingPage />} />
            <Route path="/patterns" element={<PatternsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster
        theme="dark"
        position="bottom-right"
        toastOptions={{
          style: {
            background: "#1E2220",
            border: "1px solid #2E3330",
            color: "#E8E3D9",
            fontFamily: "Manrope, sans-serif",
          },
        }}
      />
    </div>
  );
}

export default App;
