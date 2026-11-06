import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Home from './pages/Home/Home';
import Documents from './pages/Documents/Documents';
import Reports from './pages/Reports/Reports';

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/documentos" element={<Documents />} />
        <Route path="/relatorios" element={<Reports />} />
      </Routes>
    </Router>
  );
}