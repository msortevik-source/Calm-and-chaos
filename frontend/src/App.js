import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import Shell from "./components/Shell";
import HomePage from "./pages/HomePage";
import ConversationPage from "./pages/ConversationPage";
import TrainingPage from "./pages/TrainingPage";
import BudgetFoodPage from "./pages/BudgetFoodPage";
import PatternsPage from "./pages/PatternsPage";
import LetterPage from "./pages/LetterPage";
import LifeUpgradesPage from "./pages/LifeUpgradesPage";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route element={<Shell />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/conversation" element={<ConversationPage />} />
            <Route path="/training" element={<TrainingPage />} />
            <Route path="/budget" element={<BudgetFoodPage />} />
            <Route path="/life-upgrades" element={<LifeUpgradesPage />} />
            <Route path="/patterns" element={<PatternsPage />} />
            <Route path="/letter" element={<LetterPage />} />
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
