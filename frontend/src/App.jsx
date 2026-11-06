import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Home from './pages/Home/Home';

export default function App() {
  return (
    <Router>
      <Routes>
        {/* Rota principal apontando para a Home */}
        <Route path="/" element={<Home />} />
        
        {/* Podes adicionar mais rotas no futuro aqui, como:
        <Route path="/documentos" element={<Documentos />} />
        */}
      </Routes>
    </Router>
  );
}