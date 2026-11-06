import { useEffect, useState } from 'react';
import { ArrowRight, Eye, EyeOff, FileText, LockKeyhole, ShieldCheck, UserRound } from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';

function mensagemErro(error) {
  const detalhe = error.response?.data?.detail;
  if (typeof detalhe === 'string') return detalhe;
  if (Array.isArray(detalhe)) {
    return detalhe.map((item) => item.msg).filter(Boolean).join(' ');
  }
  if (error.response?.data?.erro?.mensagem) return error.response.data.erro.mensagem;
  if (!error.response) return 'Não foi possível conectar ao servidor. Tente novamente.';
  return 'Não foi possível concluir a solicitação. Confira os dados e tente novamente.';
}

const inputClass = 'w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100';

export default function AuthPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, loading, login, register } = useAuth();
  const isRegister = location.pathname === '/cadastro';
  const [nome, setNome] = useState('');
  const [usuario, setUsuario] = useState('');
  const [senha, setSenha] = useState('');
  const [confirmacao, setConfirmacao] = useState('');
  const [mostrarSenha, setMostrarSenha] = useState(false);
  const [erro, setErro] = useState('');
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (user) navigate('/', { replace: true });
  }, [user, navigate]);

  const enviar = async (event) => {
    event.preventDefault();
    setErro('');

    if (isRegister && senha !== confirmacao) {
      setErro('As senhas não coincidem.');
      return;
    }

    setEnviando(true);
    try {
      if (isRegister) {
        await register({ login: usuario.trim(), nome: nome.trim(), senha });
      } else {
        await login(usuario.trim(), senha);
      }
      navigate('/', { replace: true });
    } catch (error) {
      setErro(mensagemErro(error));
    } finally {
      setEnviando(false);
    }
  };

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-500">Verificando sessão...</div>;
  }

  return (
    <main className="grid min-h-screen bg-white lg:grid-cols-[1.05fr_0.95fr]">
      <section className="relative hidden overflow-hidden bg-indigo-700 px-12 py-10 text-white lg:flex lg:flex-col lg:justify-between xl:px-20">
        <div className="absolute -right-36 -top-32 h-[28rem] w-[28rem] rounded-full border border-white/10" />
        <div className="absolute -bottom-48 -left-36 h-[34rem] w-[34rem] rounded-full border border-white/10" />
        <div className="relative flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-lg font-bold text-indigo-700">P</div>
          <span className="text-xl font-bold tracking-tight">Prioriza</span>
        </div>

        <div className="relative max-w-xl py-16">
          <span className="mb-6 inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-xs font-medium text-indigo-100">
            <ShieldCheck className="h-4 w-4" /> Gestão inteligente de documentos
          </span>
          <h1 className="text-4xl font-bold leading-tight tracking-tight xl:text-5xl">
            Seus documentos organizados. Sua rotina sob controle.
          </h1>
          <p className="mt-6 max-w-lg text-base leading-7 text-indigo-100">
            Acesse sua conta para acompanhar documentos, prazos e revisões em um só lugar.
          </p>
        </div>

        <div className="relative flex items-center gap-3 text-sm text-indigo-100">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/10">
            <FileText className="h-4 w-4" />
          </div>
          <span>OCR, classificação e acompanhamento em uma única plataforma</span>
        </div>
      </section>

      <section className="flex min-h-screen items-center justify-center px-5 py-10 sm:px-10">
        <div className="w-full max-w-md">
          <div className="mb-10 flex items-center gap-3 lg:hidden">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 font-bold text-white">p</div>
            <span className="text-lg font-bold text-slate-800">prioriza</span>
          </div>

          <div className="mb-8">
            <p className="mb-2 text-sm font-semibold text-indigo-600">{isRegister ? 'Crie sua conta' : 'Bem-vindo de volta'}</p>
            <h2 className="text-3xl font-bold tracking-tight text-slate-900">
              {isRegister ? 'Comece agora' : 'Entre na sua conta'}
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              {isRegister ? 'Preencha seus dados para acessar o Prioriza.' : 'Informe seus dados para continuar.'}
            </p>
          </div>

          <div className="mb-7 grid grid-cols-2 rounded-xl bg-slate-100 p-1">
            <Link
              to="/login"
              className={`rounded-lg px-3 py-2.5 text-center text-sm font-semibold transition ${!isRegister ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
            >
              Entrar
            </Link>
            <Link
              to="/cadastro"
              className={`rounded-lg px-3 py-2.5 text-center text-sm font-semibold transition ${isRegister ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
            >
              Criar conta
            </Link>
          </div>

          <form onSubmit={enviar} className="space-y-5">
            {isRegister && (
              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">Nome completo</span>
                <input
                  autoComplete="name"
                  className={inputClass}
                  maxLength={200}
                  minLength={1}
                  onChange={(event) => setNome(event.target.value)}
                  placeholder="Como podemos chamar você?"
                  required
                  value={nome}
                />
              </label>
            )}

            <label className="block space-y-2">
              <span className="text-sm font-medium text-slate-700">Usuário</span>
              <span className="relative block">
                <UserRound className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  autoComplete="username"
                  className={`${inputClass} pl-11`}
                  maxLength={100}
                  minLength={3}
                  onChange={(event) => setUsuario(event.target.value)}
                  placeholder="Seu nome de usuário"
                  required
                  value={usuario}
                />
              </span>
            </label>

            <label className="block space-y-2">
              <span className="text-sm font-medium text-slate-700">Senha</span>
              <span className="relative block">
                <LockKeyhole className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  autoComplete={isRegister ? 'new-password' : 'current-password'}
                  className={`${inputClass} pl-11`}
                  maxLength={200}
                  minLength={isRegister ? 8 : undefined}
                  onChange={(event) => setSenha(event.target.value)}
                  placeholder={isRegister ? 'Mínimo de 8 caracteres' : 'Digite sua senha'}
                  required
                  type={mostrarSenha ? 'text' : 'password'}
                  value={senha}
                />
                <button
                  aria-label={mostrarSenha ? 'Ocultar senha' : 'Mostrar senha'}
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 text-slate-400 hover:text-slate-700"
                  onClick={() => setMostrarSenha((mostrar) => !mostrar)}
                  type="button"
                >
                  {mostrarSenha ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </span>
            </label>

            {isRegister && (
              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">Confirme sua senha</span>
                <input
                  autoComplete="new-password"
                  className={inputClass}
                  maxLength={200}
                  minLength={8}
                  onChange={(event) => setConfirmacao(event.target.value)}
                  placeholder="Digite a senha novamente"
                  required
                  type="password"
                  value={confirmacao}
                />
              </label>
            )}

            {erro && (
              <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                {erro}
              </p>
            )}

            <button
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 focus:outline-none focus:ring-4 focus:ring-indigo-200 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={enviando}
              type="submit"
            >
              {enviando ? 'Aguarde...' : isRegister ? 'Criar minha conta' : 'Entrar'}
              {!enviando && <ArrowRight className="h-4 w-4" />}
            </button>
          </form>

          <p className="mt-8 text-center text-xs leading-5 text-slate-400">
            Ao continuar, você concorda com os termos de uso e a política de privacidade.
          </p>
        </div>
      </section>
    </main>
  );
}
