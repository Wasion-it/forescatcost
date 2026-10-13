import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { PERM, useAuth } from "../auth/Autenticacao";

interface Item {
  para: string;
  rotulo: string;
  permissao: string;
}

const GRUPOS: { titulo: string; itens: Item[] }[] = [
  {
    titulo: "Operação",
    itens: [
      { para: "/", rotulo: "Painel", permissao: PERM.provisaoLer },
      { para: "/importacoes", rotulo: "Importações", permissao: PERM.importacaoLer },
    ],
  },
  {
    titulo: "Financeiro",
    itens: [{ para: "/provisoes", rotulo: "Provisões", permissao: PERM.provisaoLer }],
  },
  {
    titulo: "Regras de cálculo",
    itens: [
      { para: "/parametros", rotulo: "Parâmetros", permissao: PERM.parametroLer },
      { para: "/aliquotas", rotulo: "Alíquotas", permissao: PERM.parametroLer },
      { para: "/formulas", rotulo: "Fórmulas", permissao: PERM.parametroLer },
      { para: "/cadastros", rotulo: "Parceiros e terminais", permissao: PERM.parametroLer },
    ],
  },
  {
    titulo: "Administração",
    itens: [
      { para: "/usuarios", rotulo: "Usuários", permissao: PERM.usuarioGerir },
      { para: "/auditoria", rotulo: "Auditoria", permissao: PERM.auditoriaLer },
    ],
  },
];

export function Layout() {
  const { usuario, pode, sair } = useAuth();
  const [aberto, setAberto] = useState(false);
  const local = useLocation();

  return (
    <div className="app">
      <aside className="trilho" data-aberto={aberto} aria-label="Navegação principal">
        <NavLink to="/" className="marca" onClick={() => setAberto(false)}>
          <span className="marca-simbolo" aria-hidden="true" />
          <span className="marca-nome">
            Forecast
            <small>Previsão de custos de importação</small>
          </span>
        </NavLink>
        <nav>
          {GRUPOS.map((g) => {
            const visiveis = g.itens.filter((i) => pode(i.permissao));
            if (visiveis.length === 0) return null;
            return (
              <div className="trilho-grupo" key={g.titulo}>
                <p id={`grupo-${g.titulo}`}>{g.titulo}</p>
                <ul aria-labelledby={`grupo-${g.titulo}`}>
                  {visiveis.map((i) => (
                    <li key={i.para}>
                      <NavLink to={i.para} end={i.para === "/"} onClick={() => setAberto(false)}>
                        {i.rotulo}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </nav>
        <div className="trilho-usuario">
          <strong>{usuario?.nome}</strong>
          <span>{usuario?.perfis.map((p) => p.nome).join(", ")}</span>
          <br />
          <button type="button" onClick={sair}>
            Sair
          </button>
        </div>
      </aside>
      <main className="conteudo" id="conteudo" key={local.pathname.split("/")[1]}>
        <button type="button" className="botao menu-movel" aria-expanded={aberto} onClick={() => setAberto((a) => !a)}>
          Menu
        </button>
        <Outlet />
      </main>
    </div>
  );
}
