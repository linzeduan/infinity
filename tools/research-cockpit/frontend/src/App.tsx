import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import AskPage from "./pages/AskPage";
import DashboardPage from "./pages/DashboardPage";
import LibraryPage from "./pages/LibraryPage";
import PredictionsPage from "./pages/PredictionsPage";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/ask" element={<AskPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/predictions" element={<PredictionsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
