# Sompo Predict T1 — Sprint 1

Prototipo funcional simulado para o desafio FIAP × Sompo Seguros 2026.
**Squad T1** · Scrum Master: Rafael (Gon) · Devs: Charles, Anthony, Guilherme, Gustavo.

> **Sompo Predict reduz sinistros agrícolas detectando padrões de risco em tempo real.**

---

## Stack

- **Python 3.10+**
- **Streamlit** — frontend unico
- **PyJWT + cryptography.Fernet** — autenticacao + cripto AES
- **scikit-learn** — Decision Tree (motor de risco), Isolation Forest (anomalias)
- **pandas, numpy** — manipulacao de dados

Custo total: **R$ 0** (free tier AWS + libs open-source).

---

## Como rodar localmente

```bash
git clone <repo>
cd projeto-t1
pip install -r requirements.txt
streamlit run app.py
```

**Credenciais default (demo):**
```
usuario: admin
senha:   admin123
perfil:  Admin
```

---

## Estrutura

```
projeto-t1/
├── app.py                 → roteador principal (Charles)
├── core_auth.py           → login, JWT, RBAC (Charles)
├── core_audit.py          → trilha de auditoria SHA-256 (Charles)
├── dashboard_cliente.py   → painel US03 do segurado (Charles)
│
├── pagina_anthony.py      → telemetria IoT (Anthony — US04)
├── pagina_guilherme.py    → analise de dados (Guilherme — US06/08)
├── pagina_gustavo.py      → cloud + IA (Gustavo — US05)
├── pagina_rafael.py       → XAI + ranking (Rafael — US07)
│
├── pagina_TEMPLATE.py     → template pra novos modulos
├── test_pagina_local.py   → helper de dev (bypass login)
├── requirements.txt
└── README.md
```

---

## Contrato pros membros do squad

Cada `pagina_NOME.py` deve seguir essas 8 regras:

1. Expor uma funcao `def render():` — sem args, sem retorno.
2. Importar `from core_audit import gerar_trilha_auditoria`.
3. Chamar `gerar_trilha_auditoria()` em toda acao relevante.
4. **NAO usar** `st.set_page_config` — apenas o `app.py` faz isso.
5. **NAO fazer login** dentro da pagina — quando ela roda, o usuario ja esta logado.
6. Usar `key=` em todos os widgets, prefixado com seu nome (ex: `key="anthony_slider1"`).
7. Imports pesados (shap, tensorflow) ficam **dentro** de `render()` (lazy).
8. Nao escrever no `st.session_state` em chaves nao prefixadas com seu nome.

**Deadline pra integracao:** SEXTA 01/05 as 20h.

---

## RBAC (matriz de permissoes)

| Perfil | Permissoes |
|--------|-----------|
| **Admin** | `all` (acesso total) |
| **Cientista** | `view_dashboard`, `train_models`, `extract_data` |
| **Operador** | `view_dashboard`, `input_telemetry` |

---

## Trilha de Auditoria

Todo log gerado e:

1. **Estruturado em Canonical JSON** (chaves ordenadas, sem espacos — hash deterministico)
2. **Encadeado via SHA-256** (cada hash referencia o anterior atraves do campo `prev_hash` — adulterar 1 log quebra a cadeia toda)
3. **Criptografado com Fernet** (AES-128-CBC + HMAC SHA-256) antes de armazenar
4. **Visivel no expander do rodape** em cada pagina

Esse mecanismo cobre os requisitos da disciplina de **Seguranca da Informacao**:
- Etapa 2: RBAC + fluxograma de autenticacao
- Etapa 3: pipeline de validacao de integridade (hash chaining)
- Etapa 4: armazenamento criptografado + logs estruturados (LGPD)

---

## Workflow de desenvolvimento

```bash
# 1. Cada membro desenvolve sua pagina isoladamente
streamlit run test_pagina_local.py   # bypassa login

# 2. Quando estiver pronto, rodar a app completa pra testar integracao
streamlit run app.py

# 3. Commit e push na branch dev
git checkout -b dev/anthony
git commit -am "feat(anthony): pagina iot com wokwi"
git push origin dev/anthony

# 4. Charles faz merge na main no sabado 02/05 (call de integracao)
```

---

## Cronograma Sprint 1

| Data | Atividade |
|------|-----------|
| 30/04 (qui) | Charles termina core (auth + auditoria) |
| 01/05 (sex) | **Deadline 20h:** todos entregam suas paginas |
| 02/05 (sab) | Call de integracao (14h-16h) |
| 03/05 (dom) | Polimento + video Trello + relatorios |
| 04/05 (seg) | Ensaio 1 do pitch |
| 05/05 (ter) | Ensaio final |
| 06/05 (qua) | **PITCH SOMPO 🎤** |
| 10/05 (sab) | Deadline final dos entregaveis no portal FIAP |

---

## User Stories cobertas

| ID | Persona | Modulo |
|----|---------|--------|
| US01 | Sompo (Risk Analyst) | Decision Tree no `core_audit` (motor de risco) |
| US02 | Sompo (Compliance) | Trilha de auditoria imutavel |
| US03 | Cliente Segurado | `dashboard_cliente.py` |
| US04 | Operador de Equipamento | `pagina_anthony.py` |
| US05 | Gestor de Frota | `pagina_gustavo.py` (Cloud) |
| US06 | Tecnico de Manutencao | `pagina_guilherme.py` (Anomalias) |
| US07 | Analista de Subscricao | `pagina_rafael.py` (XAI/SHAP) |
| US08 | Analista de Sinistros | `pagina_guilherme.py` (caixa-preta via auditoria) |

---

## Referencias e Fontes

- [Sompo Seguros — Equipamentos Agricolas](https://www.sompo.com.br/empresas/agronegocio/)
- [SUSEP — Dados Estatisticos](http://www2.susep.gov.br/menuestatistica/SES/principal.aspx)
- [Open-Meteo API (clima)](https://open-meteo.com/)
- [INMET — Banco de Dados Meteorologicos](https://bdmep.inmet.gov.br/)
- [LGPD — Lei 13.709/2018](http://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
