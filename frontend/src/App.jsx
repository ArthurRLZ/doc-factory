import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Home from './pages/Home/Home';
import Documents from './pages/Documents/Documents';

export default function App() {
  return (
    <Router>
      <Routes>
        {/* Rota principal apontando para a Home */}
        <Route path="/" element={<Home />} />
        <Route path="/documentos" element={<Documents />} />
        {/* Podes adicionar mais rotas no futuro aqui, como:
        <Route path="/documentos" element={<Documentos />} />
        */}
      </Routes>
    </Router>
  );
}