import type { ReactElement } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { PERM, useAuth } from "./auth/Autenticacao";
import { Entrar } from "./auth/Entrar";
import { Carregando } from "./componentes/comuns";
import { Layout } from "./componentes/Layout";
import { Auditoria } from "./paginas/admin/Auditoria";
import { Usuarios } from "./paginas/admin/Usuarios";
import { DetalheImportacao } from "./paginas/importacoes/Detalhe";
import { FormularioImportacao } from "./paginas/importacoes/Formulario";
import { ListaImportacoes } from "./paginas/importacoes/Lista";
import { Painel } from "./paginas/Painel";
import { Provisoes } from "./paginas/Provisoes";
import { Aliquotas } from "./paginas/regras/Aliquotas";
import { Cadastros } from "./paginas/regras/Cadastros";
import { Formulas } from "./paginas/regras/Formulas";
import { Parametros } from "./paginas/regras/Parametros";

function Protegida({ permissao, children }: { permissao: string; children: ReactElement }) {
  const { pode } = useAuth();
  if (!pode(permissao)) {
    return (
      <div className="vazio">
        <p>Seu perfil não tem acesso a esta área. Fale com o administrador se precisar dela.</p>
      </div>
    );
  }
  return children;
}

export function App() {
  const { usuario, carregando } = useAuth();
  if (carregando) return <Carregando texto="Abrindo sua sessão…" />;
  if (!usuario) {
    return (
      <Routes>
        <Route path="*" element={<Entrar />} />
      </Routes>
    );
  }
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Protegida permissao={PERM.provisaoLer}><Painel /></Protegida>} />
        <Route path="importacoes" element={<Protegida permissao={PERM.importacaoLer}><ListaImportacoes /></Protegida>} />
        <Route path="importacoes/nova" element={<Protegida permissao={PERM.importacaoEditar}><FormularioImportacao /></Protegida>} />
        <Route path="importacoes/:id" element={<Protegida permissao={PERM.importacaoLer}><DetalheImportacao /></Protegida>} />
        <Route path="importacoes/:id/editar" element={<Protegida permissao={PERM.importacaoEditar}><FormularioImportacao /></Protegida>} />
        <Route path="provisoes" element={<Protegida permissao={PERM.provisaoLer}><Provisoes /></Protegida>} />
        <Route path="parametros" element={<Protegida permissao={PERM.parametroLer}><Parametros /></Protegida>} />
        <Route path="aliquotas" element={<Protegida permissao={PERM.parametroLer}><Aliquotas /></Protegida>} />
        <Route path="formulas" element={<Protegida permissao={PERM.parametroLer}><Formulas /></Protegida>} />
        <Route path="cadastros" element={<Protegida permissao={PERM.parametroLer}><Cadastros /></Protegida>} />
        <Route path="usuarios" element={<Protegida permissao={PERM.usuarioGerir}><Usuarios /></Protegida>} />
        <Route path="auditoria" element={<Protegida permissao={PERM.auditoriaLer}><Auditoria /></Protegida>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
