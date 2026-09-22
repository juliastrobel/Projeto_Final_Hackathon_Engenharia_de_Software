# Hackathon IFPR Pinhais — Sistema de Apoio

Sistema de apoio ao 1º Hackathon do curso de Ciência da Computação do IFPR Campus Pinhais, desenvolvido como projeto integrador da disciplina **Engenharia de Software I**.

O sistema cobre todo o ciclo do evento: inscrição de equipes, verificação automatizada de legitimidade das submissões via GitHub, avaliação pela banca examinadora e divulgação pública dos resultados.

📄 Para decisões de design mais detalhadas, consulte a [Wiki do projeto](../../wiki).

---

## Funcionalidades

- **Inscrição de equipes** (3 a 5 integrantes) com verificação de e-mail do líder
- **Autenticação via GitHub (OAuth)** para vincular a equipe ao repositório do projeto, com login recorrente sem depender de senha
- **Verificação anti-plágio automatizada**: compara a data de criação do repositório e as datas de cada commit contra a janela oficial do evento, gerando um veredito (`ok` / `suspeito`)
- **Vínculo manual de integrantes**: o líder da equipe associa cada nome declarado na inscrição a um contribuidor real do repositório no GitHub
- **Painel da banca examinadora**: login por link de acesso único (*magic link*), listagem de equipes com filtro por veredito automático, e registro individual de nota por jurado
- **Painel público de resultados**: ranking por média de notas, liberado apenas quando a organização decidir

---

## Arquitetura

```
Participante                          Banca examinadora
     │                                        │
     ▼                                        ▼
 Inscrição → Verificação de e-mail      Login por link único
     │                                        │
     ▼                                        ▼
 Login via GitHub (OAuth) ──────────►  Painel da banca
     │                                        │
     ▼                                        ▼
 Área da equipe                    Análise automática (API GitHub)
     │                                        │
     └──────────────► Nota do jurado ◄────────┘
                              │
                              ▼
                    Ranking público de resultados
```

O sistema é uma aplicação **monolítica**, server-side rendered (sem frontend separado), composta por:

- **Backend**: FastAPI (Python), com templates Jinja2 renderizados diretamente no servidor
- **Banco de dados**: SQLite, em arquivo único, com volume persistente na hospedagem
- **Frontend**: HTML + CSS puro (identidade visual customizada) + JavaScript vanilla para interatividade pontual (formulário dinâmico, animação do cronograma)
- **Serviços externos**: API do GitHub (OAuth e dados de repositório) e Brevo (envio de e-mails transacionais)
- **Hospedagem**: Railway, com volume persistente para o banco de dados

---

## Stack tecnológica

| Camada | Tecnologia |
|---|---|
| Linguagem | Python |
| Framework web | FastAPI + Uvicorn |
| Banco de dados | SQLite |
| Templates | Jinja2 |
| Requisições HTTP | httpx |
| Frontend | HTML, CSS, JavaScript (sem framework) |
| Ícones | Lucide Icons |
| E-mail transacional | Brevo |
| Hospedagem | Railway |
| Integração externa | API REST do GitHub |

---

## Variáveis de ambiente

O sistema não funciona sem essas variáveis configuradas (arquivo `.env` local, ou nas *Variables* da hospedagem):

### Aplicação
| Variável | Descrição |
|---|---|
| `BASE_URL` | URL pública onde a aplicação está hospedada (ex.: `https://seuapp.railway.app`) |

### GitHub OAuth
| Variável | Descrição |
|---|---|
| `GITHUB_CLIENT_ID` | Client ID do OAuth App registrado no GitHub |
| `GITHUB_CLIENT_SECRET` | Client Secret do OAuth App |
| `GITHUB_PAT` | Personal Access Token (sem escopos), usado para elevar o limite de requisições à API pública do GitHub |

### E-mail (Brevo)
| Variável | Descrição |
|---|---|
| `BREVO_API_KEY` | Chave de API da conta Brevo |
| `BREVO_SENDER_EMAIL` | E-mail remetente configurado na Brevo |

### Janela do evento (verificação anti-plágio)
| Variável | Descrição |
|---|---|
| `EVENT_START` | Data/hora de início da janela válida de commits (ISO 8601, ex.: `2026-09-23T00:00:00`) |
| `EVENT_END` | Data/hora de fim da janela válida de commits |

### Cronograma público (exibido na home)
| Variável | Descrição |
|---|---|
| `INSCRICOES_INICIO` / `INSCRICOES_FIM` | Período de inscrições |
| `VALIDACAO_INICIO` / `VALIDACAO_FIM` | Período de validação |
| `UPLOAD_INICIO` / `UPLOAD_FIM` | Período de upload dos projetos |
| `AVALIACAO_INICIO` / `AVALIACAO_FIM` | Período de avaliação da banca |
| `RESULTADOS_DATA` | Data de divulgação dos resultados |

### Divulgação de resultados
| Variável | Descrição |
|---|---|
| `RESULTS_RELEASED` | `true` ou `false` — controla se o ranking público (`/resultados`) está visível |

---

## Como rodar localmente

```bash
# clonar o repositório
git clone <url-do-repositorio>
cd <pasta-do-projeto>

# criar e ativar o ambiente virtual
python3 -m venv venv
source venv/bin/activate

# instalar as dependências
pip install -r requirements.txt

# configurar as variáveis de ambiente
cp .env.example .env
# preencher o .env com os valores reais

# rodar a aplicação
uvicorn app.main:app --reload
```

Acesse `http://localhost:8000` no navegador.

---

## Estrutura do repositório

```
app/
  main.py          # aplicação FastAPI (rotas e lógica)
templates/          # páginas HTML (Jinja2)
static/             # CSS, imagens
schema.sql          # definição das tabelas do banco (SQLite)
requirements.txt    # dependências Python
.env.example        # modelo de variáveis de ambiente (sem valores reais)
```

---

## Decisões de design (resumo)

- **Kanban em vez de Scrum**: o fluxo de trabalho foi contínuo, sem sprints em caixa de tempo fixa, com requisitos que só se tornaram claros durante o desenvolvimento (ex.: necessidade de múltiplos jurados avaliando a mesma equipe de forma independente)
- **Veredito automático separado da nota do jurado**: a análise de datas via GitHub serve como filtro de triagem, não como decisão substitutiva — a data de um commit pode, em tese, ser forjada; a data de criação do repositório no servidor do GitHub, não
- **Autenticação sem senha**: tanto jurados quanto equipes acessam via link de acesso único, eliminando o armazenamento de credenciais
- **SQLite + volume persistente**: suficiente para o volume de um hackathon de porte institucional, sem exigir infraestrutura de banco separada

Para o raciocínio completo por trás de cada decisão, veja a [Wiki do projeto](../../wiki).

---

## Equipe

- **Backend, banco de dados e infraestrutura**: Isaque Cortina Pires
- **Frontend e identidade visual**: Julia Pinheiro Strobel

---

## Licença

Este projeto está licenciado sob os termos descritos no arquivo `LICENSE`.
