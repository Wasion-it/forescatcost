import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { ProvedorAutenticacao } from "./auth/Autenticacao";
import { ErroApi } from "./lib/api";
import "./styles/global.css";
import "./styles/fita.css";

const cliente = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // Não insiste em erros de regra/autorização; só em falhas transitórias
      retry: (tentativas, erro) => !(erro instanceof ErroApi && erro.status < 500) && tentativas < 2,
    },
  },
});

createRoot(document.getElementById("raiz")!).render(
  <StrictMode>
    <QueryClientProvider client={cliente}>
      <BrowserRouter>
        <ProvedorAutenticacao>
          <App />
        </ProvedorAutenticacao>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
