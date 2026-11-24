# Dois portais, um sistema

A plataforma serve dois públicos com necessidades diferentes de detalhe.
São **duas visões do mesmo cálculo**, não dois sistemas.

| | Portal da Seguradora | Portal do Segurado |
|---|---|---|
| Marca | Sompo Predict | Minha Máquina |
| Público | Subscritor, analista, gestor | Produtor rural, operador |
| Telas | 16 | 4 |
| Porta | 8501 | 8502 |
| Conta demo | `admin` / `Admin@2024!` | `produtor` / `Produtor@2024!` |

## Executar

Os dois ao mesmo tempo:

    python iniciar_portais.py

Ou separadamente:

    streamlit run app.py                                   # seguradora

    $env:SOMPO_PERFIL = "cliente"                          # PowerShell
    streamlit run app.py --server.port 8502                # segurado

## O que o segurado NÃO vê, e por quê

| Tela ausente | Motivo |
|---|---|
| Carteira de Risco, Frota | Contêm apólices de outros clientes |
| Base de Apólices | Idem — dado de terceiros |
| Modelos, Explicabilidade, Desempenho | Detalhe técnico que não muda a decisão dele |
| Infraestrutura, Auditoria, Fontes de Dados | Operação interna da seguradora |
| Parecer de Subscrição, Sinistros | Processo interno |

Sobram quatro telas: situação atual do equipamento, histórico, simulação
de condições e os próprios dados sob a LGPD.

## Duas camadas de proteção

**Portal** — a rota que não pertence ao menu do portal é recusada antes de
executar, e a tentativa fica registrada na trilha (`ACESSO_FORA_DO_PORTAL`).
Editar o estado da sessão não contorna.

**Papel** — o papel `Segurado` não possui `view_dashboard` nem
`view_dados`. Mesmo que alcançasse uma tela de carteira, ela recusaria.

As duas são independentes: contornar uma esbarra na outra.

## Por que um código só

Duplicar o projeto faria as versões divergirem na primeira correção que
alguém esquecesse de replicar. O pior sintoma possível é o sinalizador do
produtor discordar do score do subscritor sobre o mesmo equipamento.

`core_perfis.py` descreve o que cada portal oferece. O cálculo, a
telemetria e a segurança são os mesmos arquivos.

## Na demonstração

Abra as duas janelas lado a lado e incline a máquina uma vez: o segurado vê
o sinalizador mudar de cor, a seguradora vê a apólice subir no ranking de
exposição. Uma leitura, dois destinos — comunica a arquitetura melhor que
qualquer diagrama.
