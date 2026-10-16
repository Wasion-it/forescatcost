import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { AvisoErro } from "../componentes/comuns";
import { useAuth } from "./Autenticacao";

export function Entrar() {
  const { usuario, entrar } = useAuth();
  const [login, setLogin] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  if (usuario) return <Navigate to="/" replace />;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await entrar(login.trim(), senha);
    } catch (err) {
      setErro(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="entrada-tela">
      <section className="entrada-aguas" aria-hidden="true">
        <div className="entrada-frase">
          <p>
            Do valor da invoice ao desembolso do mês: cada imposto, taxa e frete calculado com a regra vigente, e
            guardado com a sua memória de cálculo.
          </p>
        </div>
      </section>
      <section className="entrada-form">
        <form onSubmit={enviar} noValidate>
          <div className="marca marca-clara">
            <span className="marca-simbolo" aria-hidden="true" />
            <span className="marca-nome">
              Forecast
              <small>Previsão de custos de importação</small>
            </span>
          </div>
          <h1>Entrar</h1>
          <div className="campo">
            <label htmlFor="login">Usuário</label>
            <input
              id="login"
              className="entrada"
              type="text"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              required
            />
          </div>
          <div className="campo">
            <label htmlFor="senha">Senha</label>
            <input
              id="senha"
              className="entrada"
              type="password"
              autoComplete="current-password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              required
            />
          </div>
          <AvisoErro erro={erro} />
          <button className="botao botao-primario" type="submit" disabled={enviando || !login.trim() || !senha}>
            {enviando ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </section>
    </div>
  );
}
