# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Os commits do projeto seguem [Conventional Commits](https://www.conventionalcommits.org/pt-br/).

A partir da 1.0.0 as versões são publicadas pelo workflow de release, que deriva
o número dos commits. As entradas novas entram logo abaixo desta linha; a 1.0.0
foi escrita à mão e fica no fim.

<!-- versoes -->

## v1.1.0 (2026-09-18)


## v1.0.1 (2026-09-18)

### Bug Fixes

- **admin**: Corrigir o total de itens no historico de pedidos
  ([`202f150`](https://github.com/italofelipe01/cafe/commit/202f1506f5458933b3776c60233363d0d50c10f9))

- **ui**: Alinhar o botao Sair a navegacao e ampliar a logo
  ([`c77bbcd`](https://github.com/italofelipe01/cafe/commit/c77bbcd5e5748986151e6bfeb5ade8770ad01214))

- **ui**: Corrigir as tabelas em telas pequenas
  ([`3977633`](https://github.com/italofelipe01/cafe/commit/39776332c27350a9d6747775d50525dfaa3d123c))

### Continuous Integration

- Gate unico reutilizavel, actions pinadas por SHA e Dependabot
  ([`4f2037a`](https://github.com/italofelipe01/cafe/commit/4f2037ac26bfc5e5d6abcbf532dd61c0d552cab4))

### Documentation

- Guia para agentes, registro de decisoes e processo de release
  ([`b897c53`](https://github.com/italofelipe01/cafe/commit/b897c53116068507b89b90b0fda90daca15f8740))


## [1.0.0] — 2026-08-10

Primeira versão preparada para uso além de `127.0.0.1`.

### Corrigido

- **A semeadura deixou de sobrescrever o catálogo a cada inicialização.** Ela
  rodava em todo boot e reescrevia `name`, `input_type`, `sort_order` e `active`
  de registros existentes, apagando reordenações e inativações feitas na
  administração. Agora é aditiva: cria o que falta e não toca no que existe.
- Escritório e salas não terminam mais em estados contraditórios depois de um
  reinício — antes o escritório voltava "Ativo" com todas as salas inativas e
  sumia do formulário de pedido sem nenhuma explicação.
- A seleção de ambiente passou a ser usada de fato: `DevelopmentConfig` e
  `ProductionConfig` nunca eram instanciados, porque `create_app()` ia sempre
  sem argumento.
- A configuração é lida na criação da aplicação, e não no import do módulo:
  ajustar `os.environ` depois de importar `config` não tinha efeito nenhum.
- `parse_quantity` recusa o separador numérico do Python. `int("1_0")` vale 10,
  então o valor gravado podia divergir do digitado.
- Concluir um pedido duas vezes responde `409` em vez de sobrescrever
  `completed_at` e perder o horário real do atendimento.
- O modo `--background` não cria mais uma segunda aplicação — e com ela uma
  segunda conexão e semeadura — só para imprimir host e porta.
- Removidos `BASE_DIR`, `PROJECT_ROOT` e `INSTANCE_DIR`, que não eram usados.

### Adicionado

- Autenticação por perfil (copa e administração) nos painéis internos e nas
  rotas de API. O formulário de pedido segue público.
- Proteção CSRF em todos os formulários e nas requisições JSON que alteram
  estado, com o token publicado em `<meta name="csrf-token">`.
- Cabeçalhos de segurança em toda resposta, incluindo Content-Security-Policy
  sem `unsafe-inline`: o script de tema é liberado por nonce por requisição.
- Limite de requisições no envio de pedidos e nas tentativas de login.
- Recusa de subir em produção com chave de sessão padrão ou sem senhas.
- Trilha de auditoria com perfil, IP e ação, e log de aplicação com nível
  configurável e arquivo rotativo opcional.
- Migrations com Alembic, e o comando `flask db upgrade` como forma oficial de
  criar e evoluir o esquema.
- Comando `flask check-config`, que mostra a configuração efetiva sem revelar
  segredos.
- Endpoint `/health`, que responde `503` quando o banco não está acessível.
- Tela de histórico de pedidos concluídos, com filtro por período e escritório,
  totais e paginação. O dado já era gravado e nunca podia ser consultado.
- Páginas próprias de 400, 401, 404, 429 e 500, no layout do portal.
- Índices em `status`, `created_at`, `completed_at` e nas chaves estrangeiras.
- Camada de serviço em `app/services.py`, que tirou validação e acesso a dados
  das rotas e eliminou a repetição das seis telas de administração.
- CI no GitHub Actions: lint, suíte em três versões de Python, aplicação das
  migrations num banco limpo e verificação de que a semeadura é idempotente.
- Configuração do ruff e `requirements-dev.txt`.

### Alterado

- O tema é aplicado antes da primeira pintura, por `data-theme` no `<html>`.
  Antes ele era aplicado no `DOMContentLoaded` e o tema escuro piscava branco a
  cada navegação.
- A reordenação de insumos funciona pelas setas do teclado, além do arrastar,
  e só grava quando a posição realmente muda.
- O formulário de pedido funciona sem JavaScript: as salas vêm renderizadas e
  agrupadas por escritório, e o script apenas filtra os grupos.
- A validação do pedido mostra a mensagem na própria página, no lugar de um
  `alert()` do navegador.
- A interceptação de envio preserva o par `name`/`value` do botão que submeteu
  o formulário.
- Consulta de salas disponível como `GET /api/rooms`; o `POST /get_rooms`
  continua aceito por compatibilidade.
- `requirements.txt` passou a listar apenas as dependências diretas, e as de
  desenvolvimento saíram para `requirements-dev.txt`.
- Margens full-bleed derivadas do padding do painel por variável CSS, para as
  faixas encostarem nas bordas em todos os breakpoints.

### Segurança

- Sem autenticação, qualquer dispositivo da rede administrava o portal quando
  ele subia com `APP_HOST=0.0.0.0`, como o próprio README sugeria para acesso
  pelo celular. Esse era o risco mais direto do projeto.
- Destinos de redirecionamento após o login são validados: só caminhos internos
  são aceitos, para que `/login?next=` não vire um redirecionador aberto.
- Corpo de requisição limitado a 256 KB.
